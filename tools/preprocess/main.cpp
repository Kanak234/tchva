// fk-preprocess — C++20 CLI tool
// Section 12 of the build spec
//
// Converts bulk historical climate CSVs into per-grid-cell baseline statistics.
// This is a CPU-bound, single-pass, memory-bandwidth-limited workload — the
// right place for C++. It is NOT in the request path.
//
// Usage:
//   fk-preprocess --in <dir> --grid <districts.json> --out baselines.json [--bench]

#include <algorithm>
#include <charconv>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <mutex>
#include <numeric>
#include <string>
#include <string_view>
#include <thread>
#include <vector>

namespace fs = std::filesystem;

// ---------------------------------------------------------------------------
// Data structures
// ---------------------------------------------------------------------------
struct WeekAcc {
    std::vector<float> rain;
    std::vector<float> tmax;
    uint64_t skip_count = 0;

    void merge(WeekAcc& other) {
        rain.insert(rain.end(), other.rain.begin(), other.rain.end());
        tmax.insert(tmax.end(), other.tmax.begin(), other.tmax.end());
        skip_count += other.skip_count;
        other.rain.clear();
        other.tmax.clear();
    }
};

using GridWeekMap = std::map<std::string, std::array<WeekAcc, 54>>;

// ---------------------------------------------------------------------------
// Fast float parsing with std::from_chars — no locale, no exceptions
// ---------------------------------------------------------------------------
static bool parse_float(std::string_view s, float& out) {
    // Trim whitespace
    while (!s.empty() && (s.front() == ' ' || s.front() == '"')) s.remove_prefix(1);
    while (!s.empty() && (s.back() == ' ' || s.back() == '"' || s.back() == '\r')) s.remove_suffix(1);
    if (s.empty() || s == "nan" || s == "NaN" || s == "") return false;
    auto r = std::from_chars(s.data(), s.data() + s.size(), out);
    return r.ec == std::errc{};
}

// ---------------------------------------------------------------------------
// Get ISO week number from a date string "YYYY-MM-DD"
// ---------------------------------------------------------------------------
static int week_of_year(std::string_view date_str) {
    if (date_str.size() < 10) return -1;
    int year = 0, month = 0, day = 0;
    auto r1 = std::from_chars(date_str.data(), date_str.data() + 4, year);
    auto r2 = std::from_chars(date_str.data() + 5, date_str.data() + 7, month);
    auto r3 = std::from_chars(date_str.data() + 8, date_str.data() + 10, day);
    if (r1.ec != std::errc{} || r2.ec != std::errc{} || r3.ec != std::errc{}) return -1;
    // Simple ISO week calculation
    std::tm t = {};
    t.tm_year = year - 1900;
    t.tm_mon = month - 1;
    t.tm_mday = day;
    std::mktime(&t);
    return (t.tm_yday / 7) + 1;
}

// ---------------------------------------------------------------------------
// Percentile with nth_element — O(n), no full sort
// ---------------------------------------------------------------------------
static float percentile(std::vector<float>& v, double q) {
    if (v.empty()) return 0.0f;
    size_t k = static_cast<size_t>(q * (v.size() - 1));
    if (k >= v.size()) k = v.size() - 1;
    std::nth_element(v.begin(), v.begin() + k, v.end());
    return v[k];
}

// ---------------------------------------------------------------------------
// Process a single CSV file into the accumulator map
// ---------------------------------------------------------------------------
static void process_file(const fs::path& path, const std::string& grid_id, GridWeekMap& acc) {
    std::ifstream f(path, std::ios::binary);
    if (!f.is_open()) {
        std::cerr << "Cannot open: " << path << "\n";
        return;
    }

    std::string line;
    // Skip header
    if (!std::getline(f, line)) return;

    // Detect column order from header
    int col_time = -1, col_tmax = -1, col_tmin = -1, col_precip = -1;
    {
        int col = 0;
        std::string_view header(line);
        size_t pos = 0, next;
        while ((next = header.find(',', pos)) != std::string_view::npos || pos <= header.size()) {
            std::string_view field = (next == std::string_view::npos) ? header.substr(pos) : header.substr(pos, next - pos);
            if (field.find("time") != std::string_view::npos) col_time = col;
            else if (field.find("temperature_2m_max") != std::string_view::npos) col_tmax = col;
            else if (field.find("temperature_2m_min") != std::string_view::npos) col_tmin = col;
            else if (field.find("precipitation_sum") != std::string_view::npos) col_precip = col;
            ++col;
            if (next == std::string_view::npos) break;
            pos = next + 1;
        }
    }

    auto& grid_acc = acc[grid_id];
    uint64_t rows = 0, skipped = 0;

    while (std::getline(f, line)) {
        ++rows;
        // Split into columns
        std::vector<std::string_view> fields;
        fields.reserve(8);
        std::string_view sv(line);
        while (!sv.empty()) {
            size_t comma = sv.find(',');
            fields.push_back(comma == std::string_view::npos ? sv : sv.substr(0, comma));
            if (comma == std::string_view::npos) break;
            sv.remove_prefix(comma + 1);
        }

        if (col_time < 0 || col_time >= (int)fields.size()) { ++skipped; continue; }

        int week = week_of_year(fields[col_time]);
        if (week < 1 || week > 53) { ++skipped; continue; }

        float rain = 0.0f, tmax = 0.0f;
        bool ok = true;
        if (col_precip >= 0 && col_precip < (int)fields.size())
            ok &= parse_float(fields[col_precip], rain);
        if (col_tmax >= 0 && col_tmax < (int)fields.size())
            ok &= parse_float(fields[col_tmax], tmax);

        if (!ok || rain < 0 || rain > 500 || tmax < -10 || tmax > 55) {
            ++skipped;
            grid_acc[week - 1].skip_count++;
            continue;
        }

        grid_acc[week - 1].rain.push_back(rain);
        grid_acc[week - 1].tmax.push_back(tmax);
    }

    if (skipped > 0) {
        std::cerr << "[" << grid_id << "] " << path.filename().string()
                  << ": " << rows << " rows, " << skipped << " skipped\n";
    }
}

// ---------------------------------------------------------------------------
// Write baselines.json — deterministic ordering
// ---------------------------------------------------------------------------
static void write_json(const GridWeekMap& acc, const std::string& out_path) {
    std::ofstream f(out_path);
    f << "{\n";
    bool first_grid = true;
    for (auto& [grid_id, weeks] : acc) {
        if (!first_grid) f << ",\n";
        first_grid = false;
        f << "  \"" << grid_id << "\": {\n";
        f << "    \"weeks\": {\n";
        bool first_week = true;
        for (int w = 1; w <= 53; ++w) {
            auto week = weeks[w - 1]; // copy for mutation in percentile
            if (week.rain.empty()) continue;
            if (!first_week) f << ",\n";
            first_week = false;
            float r50 = percentile(week.rain, 0.50);
            float r90 = percentile(week.rain, 0.90);
            float r95 = percentile(week.rain, 0.95);
            float t50 = percentile(week.tmax, 0.50);
            float t90 = percentile(week.tmax, 0.90);
            f << "      \"" << w << "\": {"
              << "\"rain_p50\": " << r50
              << ", \"rain_p90\": " << r90
              << ", \"rain_p95\": " << r95
              << ", \"tmax_p50\": " << t50
              << ", \"tmax_p90\": " << t90
              << ", \"n_years\": " << (week.rain.size() / 7)
              << "}";
        }
        f << "\n    }\n  }";
    }
    f << "\n}\n";
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------
int main(int argc, char* argv[]) {
    std::string in_dir, grid_file, out_file = "baselines.json";
    bool bench = false;
    int threads = (int)std::thread::hardware_concurrency();
    if (threads < 1) threads = 1;

    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "--in" && i + 1 < argc) in_dir = argv[++i];
        else if (a == "--grid" && i + 1 < argc) grid_file = argv[++i];
        else if (a == "--out" && i + 1 < argc) out_file = argv[++i];
        else if (a == "--threads" && i + 1 < argc) threads = std::stoi(argv[++i]);
        else if (a == "--bench") bench = true;
        else if (a == "--help") {
            std::cout << "Usage: fk-preprocess --in <dir> --grid <districts.json> --out baselines.json [--threads N] [--bench]\n";
            return 0;
        }
    }

    if (in_dir.empty()) {
        std::cerr << "Error: --in <dir> required\n";
        return 1;
    }

    auto t0 = std::chrono::high_resolution_clock::now();

    // Collect CSV files
    std::vector<fs::path> csv_files;
    for (auto& entry : fs::directory_iterator(in_dir)) {
        if (entry.path().extension() == ".csv") csv_files.push_back(entry.path());
    }
    std::sort(csv_files.begin(), csv_files.end());

    if (csv_files.empty()) {
        std::cerr << "No CSV files found in " << in_dir << "\n";
        return 1;
    }

    std::cout << "Processing " << csv_files.size() << " CSV files with " << threads << " threads...\n";

    // Parallel processing
    GridWeekMap merged;
    std::mutex merge_mutex;
    std::vector<std::thread> workers;
    size_t files_per_thread = (csv_files.size() + threads - 1) / threads;

    for (int t = 0; t < threads; ++t) {
        size_t start = t * files_per_thread;
        size_t end = std::min(start + files_per_thread, csv_files.size());
        if (start >= csv_files.size()) break;

        workers.emplace_back([&, start, end]() {
            GridWeekMap local;
            for (size_t i = start; i < end; ++i) {
                // Use filename stem as grid_id (e.g. HZB-01.csv -> HZB-01)
                std::string grid_id = csv_files[i].stem().string();
                process_file(csv_files[i], grid_id, local);
            }
            std::lock_guard<std::mutex> lock(merge_mutex);
            for (auto& [gid, weeks] : local) {
                for (int w = 0; w < 54; ++w) merged[gid][w].merge(weeks[w]);
            }
        });
    }

    for (auto& w : workers) w.join();

    auto t1 = std::chrono::high_resolution_clock::now();
    double elapsed = std::chrono::duration<double>(t1 - t0).count();

    write_json(merged, out_file);

    std::cout << "Done in " << elapsed << "s -> " << out_file << "\n";

    if (bench) {
        uint64_t total_rows = 0;
        for (auto& [gid, weeks] : merged)
            for (auto& w : weeks) total_rows += w.rain.size();
        std::cout << "BENCH: " << total_rows << " rows in " << elapsed << "s"
                  << " (" << (uint64_t)(total_rows / elapsed) << " rows/s)\n";
    }

    return 0;
}
