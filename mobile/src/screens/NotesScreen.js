// src/screens/NotesScreen.js
//
// GET /api/notes -> {notes: [...]}. Items: id/title/content/note_type/label/
// pinned/updated_at. Cards show title + type/label chips; tap to expand the
// full content (content may be plain text or JSON for checklist-style notes).
import React, { useCallback, useEffect, useState } from "react";
import { FlatList, Pressable, Text, View } from "react-native";

import { Screen, ErrorNotice, LoadingBox } from "../components";
import { styles, palette } from "../styles";
import { listNotes } from "../api/endpoints";
import { errMsg, asText, excerpt, fmtTimestamp } from "../utils";

export default function NotesScreen({ config, navigation }) {
  const { back, home } = navigation;
  const origin = config && config.origin ? config.origin : "";
  const token = config && config.token ? config.token : "";

  const [notes, setNotes] = useState(null);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [expandedId, setExpandedId] = useState(null);

  const load = useCallback(
    async function (silent) {
      if (!silent) {
        setNotes(null);
      }
      setError("");
      try {
        const list = await listNotes(origin, token);
        setNotes(list);
      } catch (e) {
        setError(errMsg(e, "Could not load notes."));
        if (!silent) {
          setNotes([]);
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
    <Screen title="Notes" onBack={back} onAction={home} actionLabel="Home">
      {notes === null ? (
        <LoadingBox text="Loading notes..." />
      ) : (
        <FlatList
          style={styles.flex1}
          data={notes}
          keyExtractor={function (n) {
            return n.id || String(Math.random());
          }}
          contentContainerStyle={styles.listContent}
          onRefresh={onRefresh}
          refreshing={refreshing}
          ListEmptyComponent={
            <View style={styles.center}>
              <Text style={styles.centerText}>
                {error ? "Could not load notes." : "No notes yet on this server."}
              </Text>
            </View>
          }
          renderItem={function ({ item }) {
            const expanded = expandedId === item.id;
            return (
              <Pressable
                onPress={function () {
                  setExpandedId(expanded ? null : item.id);
                }}
                style={({ pressed }) => [
                  styles.card,
                  pressed ? { backgroundColor: palette.surfaceAlt } : null,
                ]}
              >
                <View style={styles.rowBetween}>
                  <Text style={[styles.cardTitle, { flex: 1 }]}>
                    {excerpt(item.title || "(untitled)", 80)}
                  </Text>
                  {item.pinned ? (
                    <Text style={[styles.badgeText, { color: palette.accent, marginLeft: 8 }]}>
                      pinned
                    </Text>
                  ) : null}
                </View>
                <View style={[styles.row, { marginTop: 4, flexWrap: "wrap" }]}>
                  {item.note_type ? (
                    <Text style={[styles.cardMeta, { marginRight: 12 }]}>
                      type: {item.note_type}
                    </Text>
                  ) : null}
                  {item.label ? (
                    <Text style={[styles.cardMeta, { marginRight: 12 }]}>label: {item.label}</Text>
                  ) : null}
                  <Text style={styles.cardMeta}>{fmtTimestamp(item.updated_at)}</Text>
                </View>
                {item.content !== "" && item.content !== null && item.content !== undefined ? (
                  <Text style={[styles.cardBody, { marginTop: 6 }]}>
                    {expanded
                      ? asText(item.content)
                      : excerpt(
                          typeof item.content === "string"
                            ? item.content
                            : JSON.stringify(item.content),
                          200
                        )}
                  </Text>
                ) : null}
              </Pressable>
            );
          }}
        />
      )}
      <ErrorNotice text={notes === null ? "" : error} />
    </Screen>
  );
}
