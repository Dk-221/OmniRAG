import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'OmniRag — Ask once. Search everything.',
  description: 'An agentic research console for documents, live data, finance and code.',
  icons: {
    icon: '/logo.png',
    shortcut: '/logo.png',
    apple: '/logo.png',
  },
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <head>
        <link rel="icon" href="/logo.png" type="image/png" />
      </head>
      <body>{children}</body>
    </html>
  )
}
