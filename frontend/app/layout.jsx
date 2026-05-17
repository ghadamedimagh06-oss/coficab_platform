import './globals.css';
import RootProvider from '../components/layout/RootProvider';

export const metadata = {
  title: 'CofICab Platform',
  description: 'AI logistics control tower for COFICAB',
};

export default function RootLayout({ children }) {
  return (
    <html lang='en' suppressHydrationWarning>
      <body>
        <RootProvider>{children}</RootProvider>
      </body>
    </html>
  );
}
