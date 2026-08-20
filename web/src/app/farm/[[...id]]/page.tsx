/**
 * Farm route — server wrapper.
 *
 * generateStaticParams lives here (server component).
 * The actual UI is in FarmClient (client component).
 *
 * Firebase Hosting rewrites /farm/* → /farm/_.html so this single
 * pre-rendered page handles every farm id at runtime.
 */
import FarmClient from "./FarmClient";

export function generateStaticParams() {
  return [{ id: ["_"] }];
}

export default function FarmPage() {
  return <FarmClient />;
}
