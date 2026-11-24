import './globals.css';
import type { Metadata } from 'next';
export const metadata: Metadata = { title: 'ValidateUAE: test a business idea before you spend on it', description: 'Decision funnel, simulation and AI research for UAE business ideas.' };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en"><head><link rel="preconnect" href="https://fonts.googleapis.com" /><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" /></head><body>
      {children}
      <footer className="footer"><div className="container">ValidateUAE is decision support, not financial or investment advice. Category priors and the simulated population are illustrative planning values; replace them with official statistics and real quotes before relying on results.</div></footer>
    </body></html>
  );
}
