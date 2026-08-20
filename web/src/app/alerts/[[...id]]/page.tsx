/**
 * Alerts route — server wrapper.
 *
 * generateStaticParams lives here (server component).
 * The actual UI is in AlertClient (client component).
 */
import AlertClient from "./AlertClient";

export function generateStaticParams() {
  return [{ id: ["_"] }];
}

export default function AlertPage() {
  return <AlertClient />;
}
