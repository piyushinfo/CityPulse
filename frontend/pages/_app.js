import "leaflet/dist/leaflet.css";
import "../styles/globals.css";
import Head from "next/head";
import { ThemeProvider } from "../lib/theme";

export default function App({ Component, pageProps }) {
  return (
    <>
      <Head>
        <title>CityPulse — Jaipur Civic Intelligence</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="theme-color" content="#06101d" />
        <meta name="description" content="CityPulse — live civic intelligence for Jaipur." />
        <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><rect width=%22100%22 height=%22100%22 rx=%2220%22 fill=%22%230b1728%22/><text x=%2250%22 y=%2272%22 text-anchor=%22middle%22 font-size=%2265%22 fill=%22%2332d7e8%22>♥</text></svg>" />
      </Head>
      <ThemeProvider><Component {...pageProps} /></ThemeProvider>
    </>
  );
}
