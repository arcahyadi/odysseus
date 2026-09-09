// src/screens/DigestScreen.js
//
// GET /api/digest/ -> {digests: [{id, date, status, summary, content}], total}.
// Each card shows date + status + summary; tap to expand the full content.
import React, { useCallback, useEffect, useState } from "react";
import { FlatList, Pressable, Text, View } from "react-native";

import { Screen, ErrorNotice, LoadingBox, StatusChip } from "../components";
import { styles, palette } from "../styles";
import { listDigests } from "../api/endpoints";
import { errMsg, asText, excerpt } from "../utils";

export default function DigestScreen({ config, navigation }) {
  const { back, home } = navigation;
  const origin = config && config.origin ? config.origin : "";
  const token = config && config.token ? config.token : "";

  const [digests, setDigests] = useState(null);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [expandedId, setExpandedId] = useState(null);

  const load = useCallback(
    async function (silent) {
      if (!silent) {
        setDigests(null);
      }
      setError("");
      try {
        const list = await listDigests(origin, token);
        setDigests(list);
      } catch (e) {
        setError(errMsg(e, "Could not load digests."));
        if (!silent) {
          setDigests([]);
        }
      }
    },
    [origin, token]
  );

  useEffect(
    function () {
      load(false);
    },
    [load]
  );

  async function onRefresh() {
    setRefreshing(true);
    try {
      await load(true);
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <Screen title="Digest" onBack={back} onAction={home} actionLabel="Home">
      {digests === null ? (
        <LoadingBox text="Loading digests..." />
      ) : (
        <FlatList
          style={styles.flex1}
          data={digests}
          keyExtractor={function (d) {
            return d.id || d.date || String(Math.random());
          }}
          contentContainerStyle={styles.listContent}
          onRefresh={onRefresh}
          refreshing={refreshing}
          ListHeaderComponent={
            <Text style={[styles.cardMeta, { marginBottom: 10 }]}>
              Daily auto-digests for the token owner. Tap a row to read it.
            </Text>
          }
          ListEmptyComponent={
            <View style={styles.center}>
              <Text style={styles.centerText}>
                {error
                  ? "Could not load digests."
                  : "No digests yet. Ask the server to generate one, or wait for the nightly job."}
              </Text>
            </View>
          }
          renderItem={function ({ item }) {
            const expanded = expandedId === (item.id || item.date);
            return (
              <Pressable
                onPress={function () {
                  setExpandedId(expanded ? null : item.id || item.date);
                }}
                style={({ pressed }) => [
                  styles.card,
                  pressed ? { backgroundColor: palette.surfaceAlt } : null,
                ]}
              >
                <View style={styles.rowBetween}>
                  <Text style={[styles.cardTitle, styles.mono]}>{item.date || "(no date)"}</Text>
                  <StatusChip value={item.status || "unknown"} />
                </View>
                {item.summary ? (
                  <Text style={[styles.cardBody, { marginTop: 6 }]}>
                    {expanded ? item.summary : excerpt(item.summary, 160)}
                  </Text>
                ) : null}
                {expanded ? (
                  <View>
                    <View style={styles.divider} />
                    {item.content ? (
                      <Text style={[styles.cardBody, { color: palette.text }]}>
                        {asText(item.content)}
                      </Text>
                    ) : (
                      <Text style={styles.cardMeta}>No content stored for this digest.</Text>
                    )}
                  </View>
                ) : null}
              </Pressable>
            );
          }}
        />
      )}
      <ErrorNotice text={digests === null ? "" : error} />
    </Screen>
  );
}
