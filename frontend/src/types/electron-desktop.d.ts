export {};

declare global {
  interface Window {
    crmDesktop?: { isElectron: boolean };
  }
}
