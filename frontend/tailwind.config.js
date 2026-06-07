/** @type {import('tailwindcss').Config} */
export default {
    darkMode: ["class"],
    content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
  	extend: {
  		fontFamily: {
  			sans: ['Inter', 'sans-serif'],
  			heading: ['"SF Pro Display"', '"SF Pro"', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
  		},
  		colors: {
  			background: '#050505',
  			foreground: '#F5F2ED',
  			card: {
  				DEFAULT: '#161616',
  				foreground: '#F5F2ED'
  			},
  			popover: {
  				DEFAULT: '#0E0E0E',
  				foreground: '#F5F2ED'
  			},
  			primary: {
  				DEFAULT: '#B8A58A',
  				foreground: '#050505'
  			},
  			secondary: {
  				DEFAULT: '#161616',
  				foreground: '#B8A58A'
  			},
  			muted: {
  				DEFAULT: '#0E0E0E',
  				foreground: '#7A7A7A'
  			},
  			accent: {
  				DEFAULT: '#D6C3A5',
  				foreground: '#050505'
  			},
  			destructive: {
  				DEFAULT: 'hsl(var(--destructive))',
  				foreground: 'hsl(var(--destructive-foreground))'
  			},
  			border: '#161616',
  			input: '#161616',
  			ring: '#B8A58A',
  			chart: {
  				'1': 'hsl(var(--chart-1))',
  				'2': 'hsl(var(--chart-2))',
  				'3': 'hsl(var(--chart-3))',
  				'4': 'hsl(var(--chart-4))',
  				'5': 'hsl(var(--chart-5))'
  			}
  		},
  		borderRadius: {
  			lg: 'var(--radius)',
  			md: 'calc(var(--radius) - 2px)',
  			sm: 'calc(var(--radius) - 4px)'
  		}
  	}
  },
  plugins: [require("tailwindcss-animate")],
}
