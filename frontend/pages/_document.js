import { Html, Head, Main, NextScript } from "next/document";

export default function Document() {
  const themeBoot = `
    (function(){
      try {
        var saved = localStorage.getItem('citypulse-theme');
        var theme = saved === 'light' || saved === 'dark' ? saved :
          (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
        document.documentElement.dataset.theme = theme;
        document.documentElement.style.colorScheme = theme;
      } catch (e) {}
    })();
  `;

  return (
    <Html lang="en">
      <Head>
        <script dangerouslySetInnerHTML={{ __html: themeBoot }} />
      </Head>
      <body>
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}
