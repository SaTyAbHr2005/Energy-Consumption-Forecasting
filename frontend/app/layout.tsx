import "./globals.css";
import SessionManager from "./SessionManager";

export const metadata = {
  title: "EnergySense | Forecast-based decision support",
  description: "Household energy forecasting and smart-grid insights.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body><SessionManager />{children}</body></html>;
}
