import './globals.css';
import type { Metadata } from 'next';
export const metadata: Metadata = { title: 'ValidateUAE: test a business idea before you spend on it', description: 'Decision funnel, simulation and AI research for UAE business ideas.' };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en"><body>
      {children}
      <footer className="footer"><div className="container">ValidateUAE is decision support, not financial or investment advice. Category priors and the simulated population are illustrative planning values; replace them with official statistics and real quotes before relying on results.</div></footer>
    </body></html>
  );
}
