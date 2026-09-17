import '@testing-library/jest-dom/vitest';

const values = new Map();
const localStorage = {
  get length() {
    return values.size;
  },
  clear() {
    values.clear();
  },
  getItem(key) {
    return values.get(String(key)) ?? null;
  },
  key(index) {
    return [...values.keys()][index] ?? null;
  },
  removeItem(key) {
    values.delete(String(key));
  },
  setItem(key, value) {
    values.set(String(key), String(value));
  },
};

Object.defineProperty(globalThis, 'localStorage', {configurable: true, value: localStorage});
Object.defineProperty(window, 'localStorage', {configurable: true, value: localStorage});
