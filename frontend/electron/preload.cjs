"use strict";

const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("crmDesktop", {
  isElectron: true
});
