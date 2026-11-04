// src/screens/HomeScreen.js
//
// Dashboard after pairing: shows the connected server and opens the feature
// screens (Chat / Memory / Digest / Notes / Plans).
import React from "react";
import { Pressable, ScrollView, Text, View } from "react-native";

import { Screen } from "../components";
import { styles, palette } from "../styles";

const FEATURES = [
  {
    key: "chat",
    title: "Chat",
    subtitle: "Pick a session, stream a reply over SSE",
  },
  {
    key: "memory",
    title: "Memory",
    subtitle: "Browse stored memories and add new ones",
  },
  {
    key: "digest",
    title: "Digest",
    subtitle: "Daily auto-digests with summaries",
  },
  {
    key: "notes",
    title: "Notes",
    subtitle: "Your saved notes",
  },
  {
    key: "plans",
    title: "Plans",
    subtitle: "Multi-step plans with progress",
  },
];

export default function HomeScreen({ config, navigation }) {
  const { go, onLogout } = navigation;
  const origin = config && config.origin ? config.origin : "";

  return (
    <Screen title="Odysseus" onAction={onLogout} actionLabel="Forget server">
      <ScrollView style={styles.flex1} contentContainerStyle={styles.content}>
        <View style={[styles.card, { marginBottom: 16 }]}>
          <Text style={styles.cardTitle}>Connected to</Text>
          <Text style={[styles.mono, { color: palette.text, fontSize: 14, marginTop: 6 }]}>
            {origin}
          </Text>
          {(config.serverName || config.serverVersion) && (
            <Text style={styles.cardMeta}>
              {config.serverName || "odysseus"}
              {config.serverVersion ? " v" + config.serverVersion : ""}
              {config.owner ? " \u00b7 owner: " + config.owner : ""}
            </Text>
          )}
          <Text style={[styles.cardMeta, { marginTop: 8 }]}>
            All requests carry{" "}
            <Text style={styles.mono}>Authorization: Bearer ody_...</Text>
            {"\n"}when a token is configured. Phones must be on the same LAN as
            the server.
          </Text>
        </View>

        {FEATURES.map(function (f) {
          return (
            <Pressable
              key={f.key}
              onPress={() => go(f.key)}
              style={({ pressed }) => [
                styles.card,
                { flexDirection: "row", alignItems: "center" },
                pressed ? { backgroundColor: palette.surfaceAlt } : null,
              ]}
            >
              <View style={{ flex: 1 }}>
                <Text style={styles.cardTitle}>{f.title}</Text>
                <Text style={styles.cardMeta}>{f.subtitle}</Text>
              </View>
              <Text style={{ color: palette.accent, fontSize: 20, marginLeft: 10 }}>
                {"\u203a"}
              </Text>
            </Pressable>
          );
        })}

        <Text style={[styles.cardMeta, { textAlign: "center", marginTop: 8 }]}>
          Chat needs a session id: open Chat and pick one from the list.
        </Text>
      </ScrollView>
    </Screen>
  );
}
