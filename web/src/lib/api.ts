/**
 * API Client — Section 22.6
 *
 * The ONLY file that calls fetch(). Scattered fetch calls are how a frontend
 * becomes impossible to change when the API contract shifts.
 *
 * It is also the only place the auth token is attached. Because every
 * request goes through req(), adding the Authorization header here
 * covers the whole app — there is no route that can accidentally
 * forget it.
 */
import { getToken } from './auth';

// Static export: no Next.js server to proxy, so the browser calls the
// backend directly via NEXT_PUBLIC_API_BASE. CORS is handled by the
// backend (see CORSMiddleware in api/main.py).
const BASE = process.env.NEXT_PUBLIC_API_BASE || '';

export class ApiError extends Error {
  code: string;
  field?: string;

  constructor(body: Record<string, unknown>) {
    const err = (body?.error ?? body?.detail ?? body) as Record<string, string> | undefined;
    super(err?.message || 'Unknown error');
    this.code = err?.code || 'UNKNOWN';
    this.field = err?.field;
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function getMockFarms(): any[] {
  if (typeof window === 'undefined') return [];
  const stored = localStorage.getItem('fk_mock_farms');
  return stored ? JSON.parse(stored) : [
    {
      farm_id: "f_demo_01",
      grid_id: "Daru / Hazaribagh NE",
      growth_stage: "Vegetative Stage",
      days_after_sowing: 14,
      village: "harli",
      crop: "paddy",
      sowing_date: "2026-08-06",
      area_ha: 1.6,
      irrigation: "mixed",
      language: "hi",
      created_at: new Date().toISOString()
    }
  ];
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function saveMockFarms(farms: any[]) {
  if (typeof window !== 'undefined') {
    localStorage.setItem('fk_mock_farms', JSON.stringify(farms));
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function handleMockRequest(path: string, init?: RequestInit): any {
  console.log("Fasal Kavach offline/demo fallback handling:", path);
  const method = init?.method || 'GET';
  const body = init?.body ? JSON.parse(init.body as string) : null;

  if (path === '/api/v1/me/farms') {
    const farms = getMockFarms();
    return { owner_uid: 'demo_user', count: farms.length, farms };
  }

  if (path === '/api/v1/farms' && method === 'POST') {
    const farms = getMockFarms();
    const newFarm = {
      farm_id: `f_demo_${Math.random().toString(36).substr(2, 9)}`,
      grid_id: "Daru / Hazaribagh NE",
      growth_stage: "Early Vegetative",
      days_after_sowing: 14,
      village: body.village || 'harli',
      crop: body.crop || 'paddy',
      sowing_date: body.sowing_date || '2026-08-06',
      area_ha: parseFloat(body.area_ha) || 1.6,
      irrigation: body.irrigation || 'mixed',
      language: body.language || 'hi',
      created_at: new Date().toISOString()
    };
    farms.push(newFarm);
    saveMockFarms(farms);
    return newFarm;
  }

  if (path.startsWith('/api/v1/farms/')) {
    const farmId = path.split('/api/v1/farms/')[1].split('/')[0].split('?')[0];
    const farms = getMockFarms();
    const farm = farms.find(f => f.farm_id === farmId) || farms[0];

    if (path.includes('/advisories')) {
      const lang = path.includes('language=en') ? 'en' : 'hi';
      return {
        farm_id: farmId,
        count: 2,
        advisories: [
          {
            advisory_id: `adv_1_${farmId}`,
            event_id: `ev_1_${farmId}`,
            farm_id: farmId,
            severity: 'MODERATE',
            rule_id: 'rule_heavy_rain',
            headline: lang === 'en' ? 'Drainage Prep for Heavy Rain' : 'भारी बारिश के लिए जल निकासी की तैयारी',
            body: lang === 'en' 
              ? 'Heavy rainfall is forecast over the next 3 days. Ensure field drainage channels are cleared to prevent waterlogging in young crops.'
              : 'अगले 3 दिनों में भारी बारिश का अनुमान है। युवा फसलों में जलभराव को रोकने के लिए खेतों की जल निकासी नालियों को साफ करना सुनिश्चित करें।',
            actions: lang === 'en'
              ? ['Clear main outlet channel.', 'Verify bund stability.', 'Postpone fertilizer application.']
              : ['मुख्य निकास नाली को साफ करें।', 'मेड़ों की स्थिरता की जांच करें।', 'उर्वरक डालने का काम स्थगित करें।'],
            spoken_script: lang === 'en'
              ? 'Heavy rain is expected. Please check your field drainage.'
              : 'भारी बारिश की चेतावनी है। कृपया अपने खेत की जल निकासी व्यवस्था दुरुस्त करें।',
            generated_by: 'gemini',
            read: false,
            window_start: new Date().toISOString(),
            window_end: new Date(Date.now() + 86400000 * 3).toISOString(),
            created_at: new Date().toISOString()
          },
          {
            advisory_id: `adv_2_${farmId}`,
            event_id: `ev_2_${farmId}`,
            farm_id: farmId,
            severity: 'LOW',
            rule_id: 'rule_normal_care',
            headline: lang === 'en' ? 'Optimal Growth Weather' : 'फसल वृद्धि के लिए अनुकूल मौसम',
            body: lang === 'en'
              ? 'Current temperature range is highly suitable for crop growth. Maintain soil moisture levels as prescribed.'
              : 'वर्तमान तापमान सीमा फसल की वृद्धि के लिए बहुत उपयुक्त है। निर्धारित आवश्यकता अनुसार मिट्टी में नमी का स्तर बनाए रखें।',
            actions: lang === 'en'
              ? ['Monitor for pest activity weekly.', 'Keep record of growth stage.']
              : ['साप्ताहिक रूप से कीटों की गतिविधि पर नज़र रखें।', 'विकास की अवस्था का रिकॉर्ड रखें।'],
            spoken_script: lang === 'en'
              ? 'Optimal temperature detected for paddy growth.'
              : 'धान की फसल के विकास के लिए अनुकूल मौसम है।',
            generated_by: 'template',
            read: true,
            window_start: new Date().toISOString(),
            window_end: new Date(Date.now() + 86400000 * 7).toISOString(),
            created_at: new Date(Date.now() - 86400000).toISOString()
          }
        ]
      };
    }

    if (method === 'PATCH') {
      const idx = farms.findIndex(f => f.farm_id === farmId);
      if (idx !== -1) {
        farms[idx] = { ...farms[idx], ...body };
        saveMockFarms(farms);
        return farms[idx];
      }
    }

    return farm;
  }

  if (path.startsWith('/api/v1/advisories/')) {
    const advId = path.split('/api/v1/advisories/')[1];
    const farmId = advId.split('_').slice(2).join('_') || 'f_demo_01';
    const farms = getMockFarms();
    const farm = farms.find(f => f.farm_id === farmId) || farms[0];
    const lang = farm.language === 'en' ? 'en' : 'hi';
    const isHeavyRain = advId.startsWith('adv_1');

    return {
      advisory_id: advId,
      event_id: `ev_${advId}`,
      farm_id: farmId,
      severity: isHeavyRain ? 'MODERATE' : 'LOW',
      rule_id: isHeavyRain ? 'rule_heavy_rain' : 'rule_normal_care',
      headline: isHeavyRain 
        ? (lang === 'en' ? 'Drainage Prep for Heavy Rain' : 'भारी बारिश के लिए जल निकासी की तैयारी')
        : (lang === 'en' ? 'Optimal Growth Weather' : 'फसल वृद्धि के लिए अनुकूल मौसम'),
      body: isHeavyRain
        ? (lang === 'en' 
            ? 'Heavy rainfall is forecast over the next 3 days. Ensure field drainage channels are cleared to prevent waterlogging in young crops.'
            : 'अगले 3 दिनों में भारी बारिश का अनुमान है। युवा फसलों में जलभराव को रोकने के लिए खेतों की जल निकासी नालियों को साफ करना सुनिश्चित करें।')
        : (lang === 'en'
            ? 'Current temperature range is highly suitable for crop growth. Maintain soil moisture levels as prescribed.'
            : 'वर्तमान तापमान सीमा फसल की वृद्धि के लिए बहुत उपयुक्त है। निर्धारित आवश्यकता अनुसार मिट्टी में नमी का स्तर बनाए रखें।'),
      actions: isHeavyRain
        ? (lang === 'en'
            ? ['Clear main outlet channel.', 'Verify bund stability.', 'Postpone fertilizer application.']
            : ['मुख्य निकास नाली को साफ करें।', 'मेड़ों की स्थिरता की जांच करें।', 'उर्वरक डालने का काम स्थगित करें।'])
        : (lang === 'en'
            ? ['Monitor for pest activity weekly.', 'Keep record of growth stage.']
            : ['साप्ताहिक रूप से कीटों की गतिविधि पर नज़र रखें।', 'विकास की अवस्था का रिकॉर्ड रखें।']),
      spoken_script: isHeavyRain
        ? (lang === 'en' ? 'Heavy rain is expected. Please check your field drainage.' : 'भारी बारिश की चेतावनी है। कृपया अपने खेत की जल निकासी व्यवस्था दुरुस्त करें।')
        : (lang === 'en' ? 'Optimal temperature detected for paddy growth.' : 'धान की फसल के विकास के लिए अनुकूल मौसम है।'),
      generated_by: isHeavyRain ? 'gemini' : 'template',
      read: false,
      window_start: new Date().toISOString(),
      window_end: new Date(Date.now() + 86400000 * 3).toISOString(),
      created_at: new Date().toISOString(),
      evidence: {
        "Temperature Max (C)": 32.5,
        "Temperature Min (C)": 24.0,
        "Precipitation Forecast (mm)": isHeavyRain ? 65.4 : 2.1,
        "Soil Moisture": "High",
        "Source": "IMD Grid (Daru NE)"
      },
      source_note: "India Meteorological Department (IMD) - 0.25 deg grid forecast",
      forecast_used: [
        { date: new Date().toISOString().split('T')[0], rain_mm: isHeavyRain ? 25.0 : 0.0, t_max_c: 32.0 },
        { date: new Date(Date.now() + 86400000).toISOString().split('T')[0], rain_mm: isHeavyRain ? 30.0 : 0.5, t_max_c: 31.0 },
        { date: new Date(Date.now() + 86400000 * 2).toISOString().split('T')[0], rain_mm: isHeavyRain ? 10.4 : 1.2, t_max_c: 30.0 }
      ]
    };
  }

  if (path.startsWith('/api/v1/weather/')) {
    return {
      grid_id: "Daru / Hazaribagh NE",
      count: 5,
      forecast: [
        { date: new Date().toISOString().split('T')[0], t_max_c: 32.5, t_min_c: 24.0, rain_mm: 5.4, humidity_pct: 85 },
        { date: new Date(Date.now() + 86400000).toISOString().split('T')[0], t_max_c: 31.0, t_min_c: 23.5, rain_mm: 12.0, humidity_pct: 90 },
        { date: new Date(Date.now() + 86400000 * 2).toISOString().split('T')[0], t_max_c: 30.0, t_min_c: 23.0, rain_mm: 22.1, humidity_pct: 95 },
        { date: new Date(Date.now() + 86400000 * 3).toISOString().split('T')[0], t_max_c: 31.5, t_min_c: 23.8, rain_mm: 3.2, humidity_pct: 88 },
        { date: new Date(Date.now() + 86400000 * 4).toISOString().split('T')[0], t_max_c: 33.0, t_min_c: 24.5, rain_mm: 0.0, humidity_pct: 80 }
      ]
    };
  }

  if (path === '/api/v1/ask' && method === 'POST') {
    const q = (body.question || '').toLowerCase();
    const lang = body.language || 'hi';
    const farmId = body.farm_id || 'f_demo_01';
    const farms = getMockFarms();
    const farm = farms.find((f: Farm) => f.farm_id === farmId) || farms[0];
    const cropName = farm ? farm.crop : 'paddy';
    
    let answer = lang === 'en' 
      ? `Sowing ${cropName} in August requires careful water management. Given the forecast of heavy rains in Daru grid, keep the drainage canals open. Apply nitrogen fertilizer only after the heavy rain ceases.`
      : `अगस्त में ${cropName === 'paddy' ? 'धान' : cropName === 'tomato' ? 'टमाटर' : cropName === 'maize' ? 'मक्का' : 'फसल'} की बुवाई के लिए जल प्रबंधन बहुत महत्वपूर्ण है। दारू ग्रिड में भारी बारिश के पूर्वानुमान को देखते हुए जल निकासी नालियों को खुला रखें। भारी बारिश रुकने के बाद ही नाइट्रोजन उर्वरक का छिड़काव करें।`;
    
    if (q.includes('कीट') || q.includes('pest') || q.includes('diseas') || q.includes('बीमारी') || q.includes('potato') || q.includes('आलू')) {
      if (cropName === 'potato') {
        answer = lang === 'en'
          ? "Monitor potato crop for late blight and aphid infestations. Apply copper-based fungicides if humidity persists above 85%."
          : "आलू की फसल में पछेती झुलसा (late blight) और चेपा (aphids) के प्रकोप पर नज़र रखें। यदि आर्द्रता 85% से अधिक बनी रहे तो तांबा आधारित कवकनाशी का छिड़काव करें।";
      } else {
        answer = lang === 'en'
          ? `Monitor ${cropName} for stem borer and blast disease. Spray Neem Oil (1500 ppm) at 5ml/L of water under clear sky conditions.`
          : `${cropName === 'paddy' ? 'धान' : cropName === 'tomato' ? 'टमाटर' : cropName === 'maize' ? 'मक्का' : 'फसल'} में तना छेदक (stem borer) और झुलसा रोग (blast) पर नज़र रखें। मौसम साफ होने पर 5 मिली प्रति लीटर पानी की दर से नीम तेल (1500 ppm) का छिड़काव करें।`;
      }
    }

    return {
      answer_text: answer,
      spoken_script: answer,
      grounded: true,
      used_context: [`Crop Calendar - ${cropName}`, "IMD Weather Forecast - Daru"],
      confidence_note: "Grounded in agronomic rules and local weather forecast"
    };
  }

  return { status: 'ok', mocked: true };
}

// ---------------------------------------------------------------------------
// Mock Mode / Connection Warning State
// ---------------------------------------------------------------------------
let isMockMode = false;
let mockModeListeners: ((active: boolean) => void)[] = [];

export function getIsMockMode() {
  return isMockMode;
}

export function subscribeToMockMode(listener: (active: boolean) => void) {
  mockModeListeners.push(listener);
  listener(isMockMode);
  return () => {
    mockModeListeners = mockModeListeners.filter(l => l !== listener);
  };
}

export function setIsMockMode(val: boolean) {
  if (isMockMode !== val) {
    isMockMode = val;
    mockModeListeners.forEach(l => l(val));
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((init?.headers as Record<string, string>) || {}),
  };

  const token = await getToken().catch(() => null);
  if (token) headers['Authorization'] = `Bearer ${token}`;

  try {
    const res = await fetch(`${BASE}${path}`, { ...init, headers });

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new ApiError(body);
    }

    setIsMockMode(false);
    return res.json();
  } catch (err) {
    if (err instanceof ApiError) {
      // Server returned a structured HTTP error (e.g. 404), meaning connection is active.
      // Do not silently fallback to mock mode for missing resource error.
      throw err;
    }
    if (process.env.NEXT_PUBLIC_DEMO_MODE === 'true') {
      try {
        setIsMockMode(true);
        return handleMockRequest(path, init) as T;
      } catch (mockErr) {
        console.error("Local mock handler failed:", mockErr);
      }
    }
    throw err;
  }
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface FarmInput {
  village: string;
  lat: number;
  lon: number;
  crop: string;
  sowing_date: string;
  area_ha: number;
  irrigation: string;
  language: string;
}

export interface Farm {
  farm_id: string;
  grid_id: string;
  growth_stage: string;
  days_after_sowing: number;
  village: string;
  crop: string;
  sowing_date: string;
  area_ha: number;
  irrigation: string;
  language: string;
  created_at: string;
}

export interface Advisory {
  advisory_id: string;
  event_id: string;
  farm_id: string;
  severity: 'LOW' | 'MODERATE' | 'SEVERE';
  rule_id: string;
  headline: string;
  body: string;
  actions: string[];
  spoken_script: string;
  generated_by: 'gemini' | 'template';
  read: boolean;
  window_start: string;
  window_end: string;
  created_at: string;
  language?: string;
}

export interface AdvisoryDetail extends Advisory {
  evidence: Record<string, string | number | boolean>;
  source_note: string;
  forecast_used: Array<{
    date: string;
    rain_mm: number;
    t_max_c: number;
  }>;
}

export interface AdvisoryList {
  farm_id: string;
  count: number;
  advisories: Advisory[];
}

export interface AskInput {
  farm_id: string;
  question: string;
  language: string;
}

export interface AskResult {
  answer_text: string;
  spoken_script: string;
  grounded: boolean;
  used_context: string[];
  confidence_note: string | null;
}

export interface WeatherForecast {
  grid_id: string;
  count: number;
  forecast: Array<{
    date: string;
    t_max_c: number;
    t_min_c: number;
    rain_mm: number;
    humidity_pct: number;
  }>;
}

// ---------------------------------------------------------------------------
// API methods — the contract from Section 18
// ---------------------------------------------------------------------------
export const api = {
  // Farms
  createFarm: (body: FarmInput) =>
    req<Farm>('/api/v1/farms', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getFarm: (id: string) =>
    req<Farm>(`/api/v1/farms/${id}`),

  updateFarm: (id: string, body: Partial<FarmInput>) =>
    req<Farm>(`/api/v1/farms/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  // Advisories
  advisories: (farmId: string, language: string = 'hi') =>
    req<AdvisoryList>(`/api/v1/farms/${farmId}/advisories?language=${language}`),

  advisoryDetail: (id: string) =>
    req<AdvisoryDetail>(`/api/v1/advisories/${id}`),

  // Ask (Bolo Kisan)
  ask: (body: AskInput) =>
    req<AskResult>('/api/v1/ask', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  // Weather
  weather: (gridId: string) =>
    req<WeatherForecast>(`/api/v1/weather/${gridId}`),

  // Feedback
  feedback: (body: { advisory_id: string; farm_id: string; helpful: boolean; acted: boolean }) =>
    req<Record<string, string>>('/api/v1/feedback', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  // Internal
  triggerIngest: () =>
    req<Record<string, unknown>>('/internal/ingest', { method: 'POST' }),

  seedData: () =>
    req<Record<string, unknown>>('/internal/seed', { method: 'POST' }),

  // The signed-in user's own farms — how the app finds your farm after
  // a sign-in on a new device, without trusting localStorage.
  myFarms: () =>
    req<{ owner_uid: string; count: number; farms: Farm[] }>('/api/v1/me/farms'),

  // Health
  health: () => req<Record<string, string>>('/healthz'),

  // Is the backend actually persisting? Check before demoing.
  storageStatus: () =>
    req<{ backend: string; persistent: boolean; farms_stored: number }>(
      '/internal/status'
    ),
};
