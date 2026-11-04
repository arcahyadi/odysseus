// src/screens/PairingScreen.js
//
// Point this screen at a self-hosted Odysseus server on your LAN:
//   1. Server address — http://<host>:<port> (default port is 7000).
//   2. API token — ody_... minted on the server under Settings -> API tokens,
//      or via the admin web page /api/companion/pair ("Generate pairing code").
//   3. Discover (GET /api/companion/info) shows what the server is.
//      Test token (GET /api/companion/ping) verifies the credential.
//   4. Save & continue stores {origin, token} and opens the dashboard.
//
// Note on scopes: a pairing code is chat-scoped. Chat/companion routes work
// with it; Sessions/Memory/Digest/Notes/Plans list what the token's owner can
// see, so for those use a token created in Settings with the matching scopes.
import React, { useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";

import { Screen, Notice, PrimaryButton } from "../components";
import { styles, palette } from "../styles";
import { normalizeOrigin } from "../api/client";
import { companionInfo, companionPing } from "../api/endpoints";
import { errMsg } from "../utils";

export default function PairingScreen({ config, navigation }) {
  const { onPaired, back, canCancel } = navigation;

  const [originInput, setOriginInput] = useState(
    config && config.origin ? config.origin : ""
  );
  const [tokenInput, setTokenInput] = useState(
    config && config.token ? config.token : ""
  );
  const [busy, setBusy] = useState(null); // null | "discover" | "test" | "save"
  const [info, setInfo] = useState(null); // server info from /api/companion/info
  const [notice, setNotice] = useState(null); // { tone, text }

  const origin = normalizeOrigin(originInput);
  const token = tokenInput.trim();

  function show(tone, text) {
    setNotice({ tone: tone, text: text });
  }

  async function runDiscover() {
    if (!origin) {
      show("warn", "Enter the server address first, e.g. http://192.168.1.50:7000");
      return;
    }
    setBusy("discover");
    setNotice(null);
    setInfo(null);
    try {
      const result = await companionInfo(origin, token);
      setInfo(result);
      const caps = [];
      if (result.capabilities) {
        if (result.capabilities.chat) caps.push("chat");
        if (result.capabilities.streaming) caps.push("streaming");
      }
      show(
        "ok",
        "Server reachable: " +
          (result.name || "odysseus") +
          (result.version ? " v" + result.version : "") +
          (caps.length ? " \u2014 capabilities: " + caps.join(", ") : "") +
          (result.owner ? " \u2014 owner: " + result.owner : "")
      );
    } catch (e) {
      setInfo(null);
      if (e && e.status === 401) {
        show(
          "warn",
          "Server is reachable but requires authentication. Enter an API token (ody_...) below, or re-check the address."
        );
      } else {
        show("error", "Could not reach the server: " + errMsg(e));
      }
    } finally {
      setBusy(null);
    }
  }

  async function runTest() {
    if (!origin) {
      show("warn", "Enter the server address first, e.g. http://192.168.1.50:7000");
      return;
    }
    if (!token) {
      show(
        "warn",
        "Nothing to test yet: enter an API token (ody_...), or leave it blank only if the server runs with auth disabled."
      );
      return;
    }
    setBusy("test");
    setNotice(null);
    try {
      const p = await companionPing(origin, token);
      if (p.ok) {
        show(
          "ok",
          "Token accepted (" +
            (p.auth === "token" ? "Bearer API token" : "session") +
            ") on " +
            (p.name || "odysseus") +
            (p.version ? " v" + p.version : "") +
            "."
        );
      } else {
        show("error", "Ping answered but ok=false.");
      }
    } catch (e) {
      show("error", "Connection test failed: " + errMsg(e));
    } finally {
      setBusy(null);
    }
  }

  async function saveAndContinue() {
    if (!origin) {
      show("warn", "Enter the server address first, e.g. http://192.168.1.50:7000");
      return;
    }
    setBusy("save");
    setNotice(null);
    try {
      // Best-effort quick connectivity check before leaving the screen; the
      // config is saved regardless (an auth-disabled server has no token).
      if (token) {
        try {
          await companionPing(origin, token);
        } catch (e) {
          // surface the result after saving instead of blocking
          show(
            "warn",
            "Saved, but the token check failed: " +
              errMsg(e) +
              ". You can fix it from the Home screen."
          );
        }
      }
      await onPaired({
        origin: origin,
        token: token,
        serverName: info && info.name ? info.name : "",
        serverVersion: info && info.version ? info.version : "",
        owner: info && info.owner ? info.owner : "",
        capabilities: info && info.capabilities ? info.capabilities : {},
      });
    } catch (e) {
      show("error", "Could not save settings: " + errMsg(e));
    } finally {
      setBusy(null);
    }
  }

  const busyNow = busy !== null;

  return (
    <Screen title="Pair with Odysseus" onBack={canCancel ? back : undefined}>
      <KeyboardAvoidingView
        style={styles.flex1}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView style={styles.flex1} contentContainerStyle={styles.content}>
          <Text style={[styles.cardBody, { marginBottom: 14 }]}>
            Connect this phone to your self-hosted Odysseus server on the same
            network. The server must be reachable at the address below and bind
            to your LAN (APP_BIND=0.0.0.0, port 7000 by default).
          </Text>

          <View style={styles.field}>
            <Text style={styles.inputLabel}>Server address</Text>
            <TextInput
              style={styles.input}
              value={originInput}
              onChangeText={setOriginInput}
              placeholder="http://192.168.1.50:7000"
              placeholderTextColor={palette.textMuted}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="url"
              editable={!busyNow}
            />
          </View>

          <View style={styles.field}>
            <Text style={styles.inputLabel}>{"API token (ody_...) \u2014 optional"}</Text>
            <TextInput
              style={styles.input}
              value={tokenInput}
              onChangeText={setTokenInput}
              placeholder="ody_..."
              placeholderTextColor={palette.textMuted}
              autoCapitalize="none"
              autoCorrect={false}
              editable={!busyNow}
            />
            <Text style={[styles.cardMeta, { marginTop: 6 }]}>
              {"Minted on the server: Settings \u2192 API tokens, or the admin \"Pair a device\" page (/api/companion/pair). Chat-scoped codes work for chat + companion endpoints; data screens need a token with the matching scopes for your user."}
            </Text>
          </View>

          <Notice tone={notice ? notice.tone : "info"} text={notice ? notice.text : ""} />

          {info ? (
            <View style={styles.card}>
              <Text style={styles.cardTitle}>
                {info.name || "odysseus"}
                {info.version ? "  v" + info.version : ""}
              </Text>
              {info.owner ? (
                <Text style={styles.cardMeta}>Owner: {info.owner}</Text>
              ) : null}
              {info.capabilities ? (
                <Text style={styles.cardMeta}>
                  Capabilities: {Object.keys(info.capabilities).join(", ") || "none reported"}
                </Text>
              ) : null}
            </View>
          ) : null}

          <View style={[styles.buttonRow, { marginTop: 4 }]}>
            <PrimaryButton
              label={busy === "discover" ? "Discovering..." : "Discover server"}
              secondary
              disabled={busyNow}
              onPress={runDiscover}
            />
            <PrimaryButton
              label={busy === "test" ? "Testing..." : "Test token"}
              secondary
              disabled={busyNow}
              onPress={runTest}
            />
          </View>

          <View style={{ marginTop: 14 }}>
            <PrimaryButton
              label={busy === "save" ? "Saving..." : "Save \u0026 continue"}
              disabled={busyNow}
              onPress={saveAndContinue}
            />
          </View>

          <Text style={[styles.cardMeta, { marginTop: 16, lineHeight: 18 }]}>
            {"Tip: the web pairing page shows a payload of the form:\n{v:1, host:\"192.168.x.x\", port:7000, token:\"ody_...\"} \u2014 type http://host:port here and paste the token."}
          </Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </Screen>
  );
}
