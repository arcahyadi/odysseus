// src/screens/MemoryScreen.js
//
// GET /api/memory (list) + POST /api/memory/add. Memory items carry
// id/text/category/source/timestamp(seconds)/uses. The insert route on the
// server is /api/memory/add (a bare POST /api/memory does not exist).
import React, { useCallback, useEffect, useState } from "react";
import {
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Text,
  TextInput,
  View,
} from "react-native";

import { Screen, ErrorNotice, LoadingBox, Notice, PrimaryButton } from "../components";
import { styles, palette } from "../styles";
import { listMemories, addMemory } from "../api/endpoints";
import { errMsg, fmtTimestamp, excerpt } from "../utils";

export default function MemoryScreen({ config, navigation }) {
  const { back, home } = navigation;
  const origin = config && config.origin ? config.origin : "";
  const token = config && config.token ? config.token : "";

  const [memories, setMemories] = useState(null); // null = loading
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const [text, setText] = useState("");
  const [category, setCategory] = useState("");
  const [adding, setAdding] = useState(false);
  const [addNotice, setAddNotice] = useState(null); // { tone, text }

  const load = useCallback(
    async function (silent) {
      if (!silent) {
        setMemories(null);
      }
      setError("");
      try {
        const list = await listMemories(origin, token);
        setMemories(list);
      } catch (e) {
        setError(errMsg(e, "Could not load memories."));
        if (!silent) {
          setMemories([]);
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

  async function onAdd() {
    const trimmed = text.trim();
    if (!trimmed) {
      setAddNotice({ tone: "warn", text: "Write something to remember first." });
      return;
    }
    setAdding(true);
    setAddNotice(null);
    try {
      const resp = await addMemory(origin, token, trimmed, { category: category.trim() });
      setText("");
      setCategory("");
      const msg =
        resp && typeof resp.message === "string"
          ? resp.message
          : "Memory saved (count: " + (resp && resp.count !== undefined ? resp.count : "?") + ").";
      setAddNotice({ tone: "ok", text: msg });
      await load(true);
    } catch (e) {
      setAddNotice({ tone: "error", text: "Add failed: " + errMsg(e) });
    } finally {
      setAdding(false);
    }
  }

  const addForm = (
    <View style={{ marginBottom: 14 }}>
      <Text style={[styles.cardTitle, { marginBottom: 8 }]}>Add a memory</Text>
      <TextInput
        style={[styles.textArea, { minHeight: 64 }]}
        value={text}
        onChangeText={setText}
        placeholder='e.g. "Prefer iced coffee in the morning"'
        placeholderTextColor={palette.textMuted}
        multiline
      />
      <View style={[styles.rowBetween, { marginTop: 8 }]}>
        <TextInput
          style={[styles.input, { flex: 1, marginRight: 10 }]}
          value={category}
          onChangeText={setCategory}
          placeholder="category (optional)"
          placeholderTextColor={palette.textMuted}
          autoCapitalize="none"
        />
        <PrimaryButton
          label={adding ? "Saving..." : "Save memory"}
          disabled={adding}
          onPress={onAdd}
          small
        />
      </View>
      <Notice tone={addNotice ? addNotice.tone : "info"} text={addNotice ? addNotice.text : ""} />
    </View>
  );

  return (
    <Screen title="Memory" onBack={back} onAction={home} actionLabel="Home">
      <KeyboardAvoidingView
        style={styles.flex1}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        {memories === null ? (
          <LoadingBox text="Loading memories..." />
        ) : (
          <FlatList
            style={styles.flex1}
            data={memories}
            keyExtractor={function (m) {
              return m.id || m.text || String(Math.random());
            }}
            contentContainerStyle={styles.listContent}
            ListHeaderComponent={addForm}
            onRefresh={onRefresh}
            refreshing={refreshing}
            ListEmptyComponent={
              <View style={styles.center}>
                <Text style={styles.centerText}>
                  {error ? "Could not load memories." : "No memories yet \u2014 add your first one above."}
                </Text>
              </View>
            }
            renderItem={function ({ item }) {
              return (
                <View style={styles.card}>
                  <Text style={[styles.cardTitle, { fontWeight: "600" }]}>
                    {excerpt(item.text, 300)}
                  </Text>
                  <Text style={styles.cardMeta}>
                    {item.category ? item.category + " \u00b7 " : ""}
                    {item.source ? item.source + " \u00b7 " : ""}
                    {fmtTimestamp(item.timestamp)}
                  </Text>
                </View>
              );
            }}
          />
        )}
        <ErrorNotice text={memories === null ? "" : error} />
      </KeyboardAvoidingView>
    </Screen>
  );
}
