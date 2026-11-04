// src/AppNavigator.js
//
// Minimal, dependency-free navigation: a stack of route names rendered
// directly. No react-navigation is needed for a scaffold of this size.
//
// Routes: "pairing" (no config yet), "home" (dashboard), then one route per
// feature screen ("chat" | "memory" | "digest" | "notes" | "plans").
import React, { useCallback, useEffect, useState } from "react";
import { View } from "react-native";
import { StatusBar } from "expo-status-bar";

import { DEFAULT_CONFIG, loadConfig, saveConfig, clearConfig } from "./api/client";
import { LoadingBox } from "./components";
import { palette } from "./styles";

import PairingScreen from "./screens/PairingScreen";
import HomeScreen from "./screens/HomeScreen";
import ChatScreen from "./screens/ChatScreen";
import MemoryScreen from "./screens/MemoryScreen";
import DigestScreen from "./screens/DigestScreen";
import NotesScreen from "./screens/NotesScreen";
import PlansScreen from "./screens/PlansScreen";

export default function AppNavigator() {
  const [booted, setBooted] = useState(false);
  const [config, setConfig] = useState(Object.assign({}, DEFAULT_CONFIG));
  const [stack, setStack] = useState([]); // [{ name: string, params: object }]

  useEffect(() => {
    let mounted = true;
    (async function () {
      let cfg = Object.assign({}, DEFAULT_CONFIG);
      try {
        cfg = await loadConfig();
      } catch (e) {
        // keep defaults
      }
      if (!mounted) {
        return;
      }
      setConfig(cfg);
      // No saved origin -> the pairing screen is the root.
      setStack([{ name: cfg && cfg.origin ? "home" : "pairing", params: {} }]);
      setBooted(true);
    })();
    return function cleanup() {
      mounted = false;
    };
  }, []);

  // -- navigation primitives ------------------------------------------------
  const go = useCallback(function (name, params) {
    setStack(function (s) {
      return s.concat([{ name: name, params: params || {} }]);
    });
  }, []);

  const back = useCallback(function () {
    setStack(function (s) {
      return s.length > 1 ? s.slice(0, s.length - 1) : s;
    });
  }, []);

  const home = useCallback(function () {
    setStack(function (s) {
      return s.slice(0, Math.max(1, s.length - 1)).concat([{ name: "home", params: {} }]);
    });
  }, []);

  // Called by PairingScreen after the user saves a server config.
  const onPaired = useCallback(async function (cfg) {
    try {
      const saved = await saveConfig(cfg);
      setConfig(saved);
    } catch (e) {
      setConfig(cfg);
    }
    setStack([{ name: "home", params: {} }]);
  }, []);

  const onLogout = useCallback(async function () {
    try {
      const cleared = await clearConfig();
      setConfig(cleared);
    } catch (e) {
      setConfig(Object.assign({}, DEFAULT_CONFIG));
    }
    setStack([{ name: "pairing", params: {} }]);
  }, []);

  if (!booted) {
    return (
      <View style={{ flex: 1, backgroundColor: palette.bg }}>
        <StatusBar style="light" />
        <LoadingBox text="Loading Odysseus..." />
      </View>
    );
  }

  const top = stack[stack.length - 1];
  const isRoot = stack.length <= 1;

  let content;
  switch (top.name) {
    case "pairing":
      content = (
        <PairingScreen
          config={config}
          navigation={{ onPaired: onPaired, back: back, canCancel: !isRoot }}
        />
      );
      break;
    case "home":
      content = <HomeScreen config={config} navigation={{ go: go, onLogout: onLogout }} />;
      break;
    case "chat":
      content = <ChatScreen config={config} navigation={{ back: back, home: home }} />;
      break;
    case "memory":
      content = <MemoryScreen config={config} navigation={{ back: back, home: home }} />;
      break;
    case "digest":
      content = <DigestScreen config={config} navigation={{ back: back, home: home }} />;
      break;
    case "notes":
      content = <NotesScreen config={config} navigation={{ back: back, home: home }} />;
      break;
    case "plans":
      content = <PlansScreen config={config} navigation={{ back: back, home: home }} />;
      break;
    default:
      content = <HomeScreen config={config} navigation={{ go: go, onLogout: onLogout }} />;
  }

  return (
    <View style={{ flex: 1, backgroundColor: palette.bg }}>
      <StatusBar style="light" />
      {content}
    </View>
  );
}
