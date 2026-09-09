import type {Config} from 'tailwindcss';
import {tokens} from '@selery/shared';
export default {content:['./app/**/*.{ts,tsx}','./components/**/*.{ts,tsx}'],theme:{extend:{colors:tokens.color,fontFamily:{sans:['Inter','sans-serif'],mono:['JetBrains Mono','monospace']}}},plugins:[]} satisfies Config;
