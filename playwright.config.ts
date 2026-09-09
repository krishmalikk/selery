import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./tests/browser',workers:1,use:{baseURL:'http://127.0.0.1:3000',viewport:{width:1512,height:982},trace:'off'},reporter:'list',timeout:30000});
