// src/screens/ChatScreen.js
//
// Chat against a chosen session:
//  * session id is REQUIRED by POST /api/chat and /api/chat_stream, so the
//    screen first loads GET /api/sessions and lets you pick one;
//  * Send streams the reply over SSE (POST /api/chat_stream, parsed in
//    src/api/endpoints.js). The raw `data: {...}` events are rendered in a
//    simple monospace log, and deltas accumulate in the reply area.
//  * a small toggle also exercises the non-streaming POST /api/chat.
import React, { useEffect, useRef, useState } from "react";
import {
  FlatList,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { Screen, ErrorNotice, PrimaryButton } from "../components";
import { styles, palette } from "../styles";
import { listSessions, sendChatMessage, streamChatReply } from "../api/endpoints";
import { errMsg } from "../utils";

function describeEvent(ev) {
  if (ev.type === "done") {
    return "[done] stream ended";
  }
  if (ev.type === "chunk") {
    return (ev.thinking ? "[thinking] " : "[chunk] ") + ev.text;
  }
  let extra = "";
  try {
    if (ev.data !== undefined && ev.data !== null) {
      extra = " " + JSON.stringify(ev.data).slice(0, 200);
    }
  } catch (e) {
    extra = "";
  }
  return "[" + ev.type + "]" + extra;
}

export default function ChatScreen({ config, navigation }) {
  const { back, home } = navigation;
  const origin = config && config.origin ? config.origin : "";
  const token = config && config.token ? config.token : "";

  const [sessions, setSessions] = useState(null); // null = loading
  const [listError, setListError] = useState("");
  const [selected, setSelected] = useState(null);
  const [pickerOpen, setPickerOpen] = useState(false);

  const [message, setMessage] = useState("");
  const [useStreaming, setUseStreaming] = useState(true);
  const [streamState, setStreamState] = useState("idle"); // idle|streaming|done|error|stopped
  const [reply, setReply] = useState("");
  const [eventLines, setEventLines] = useState([]);
  const [lastError, setLastError] = useState("");

  const cancelRef = useRef(null);

  async function load() {
    setListError("");
    setSessions(null);
    try {
      const list = await listSessions(origin, token);
      setSessions(list);
      setSelected(function (prev) {
        if (prev && list.some(function (s) { return s.id === prev.id; })) {
          return prev;
        }
        return list.length ? list[0] : null;
      });
    } catch (e) {
      setListError(errMsg(e, "Could not load sessions."));
      setSessions([]);
    }
  }

  useEffect(function () {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function pushEvent(ev) {
    const line = describeEvent(ev);
    setEventLines(function (prev) {
      const next = prev.concat([line]);
      return next.length > 400 ? next.slice(next.length - 400) : next;
    });
    if (ev.type === "error" && ev.text) {
      setLastError(ev.text);
    }
  }

  async function send() {
    if (!selected || !message.trim()) {
      return;
    }
    const text = message.trim();
    setMessage("");
    setReply("");
    setEventLines([]);
    setLastError("");
    setStreamState("streaming");

    try {
      if (useStreaming) {
        // SSE over XMLHttpRequest (incremental). Returns a cancel() function.
        cancelRef.current = streamChatReply(origin, token, text, selected.id, {
          onEvent: function (ev) {
            pushEvent(ev);
            if (ev.type === "chunk" && !ev.thinking && ev.text) {
              setReply(function (prev) {
                return prev + ev.text;
              });
            }
          },
          onDone: function () {
            cancelRef.current = null;
            setStreamState("done");
          },
          onError: function (err) {
            cancelRef.current = null;
            const m = errMsg(err);
            if (/cancelled|aborted/i.test(m)) {
              setStreamState("stopped");
            } else {
              setLastError(m);
              setStreamState("error");
            }
          },
        });
      } else {
        // Non-streaming fallback: POST /api/chat -> {"response": "..."}.
        const out = await sendChatMessage(origin, token, text, selected.id);
        setReply(out || "");
        setEventLines([out ? "[response] " + out.slice(0, 400) : "[response] (empty)"]);
        setStreamState("done");
      }
    } catch (e) {
      setLastError(errMsg(e));
      setStreamState("error");
    }
  }

  function stop() {
    if (cancelRef.current) {
      cancelRef.current(); // triggers onError with "Cancelled by user."
      cancelRef.current = null;
    }
  }

  const streaming = streamState === "streaming";
  const canSend = !!selected && !!message.trim() && !streaming;

  const statusText =
    streamState === "streaming"
      ? "Streaming reply..."
      : streamState === "done"
      ? "Reply complete."
      : streamState === "error"
      ? "Stream failed."
      : streamState === "stopped"
      ? "Stream stopped."
      : selected
      ? "Ready."
      : "No session selected.";

  return (
    <Screen title="Chat" onBack={back} onAction={home} actionLabel="Home">
      <KeyboardAvoidingView
        style={styles.flex1}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <View style={{ flex: 1, padding: 12 }}>
          {/* --- session picker ---------------------------------------- */}
          <Pressable
            onPress={function () {
              if (sessions && sessions.length) {
                setPickerOpen(true);
              }
            }}
            style={({ pressed }) => [
              styles.card,
              { flexDirection: "row", alignItems: "center", marginBottom: 8 },
              pressed ? { backgroundColor: palette.surfaceAlt } : null,
            ]}
          >
            <View style={{ flex: 1 }}>
              <Text style={styles.cardTitle}>
                {selected
                  ? selected.name
                  : sessions === null
                  ? "Loading sessions..."
                  : sessions && sessions.length
                  ? "Pick a session"
                  : "No sessions"}
              </Text>
              <Text style={styles.cardMeta} numberOfLines={1}>
                {selected
                  ? "id " + selected.id + (selected.model ? " \u00b7 " + selected.model : "")
                  : sessions === null
                  ? "Contacting " + origin
                  : sessions && sessions.length
                  ? sessions.length + " session(s) available"
                  : listError || "Create a chat in the web UI first."}
              </Text>
            </View>
            {sessions && sessions.length ? (
              <Text style={{ color: palette.accent, fontSize: 18, marginLeft: 8 }}>
                {"\u25be"}
              </Text>
            ) : null}
          </Pressable>

          <ErrorNotice text={listError} />
          <Text style={[styles.cardMeta, { marginBottom: 8 }]}>
            {statusText}
          </Text>

          {/* --- reply area --------------------------------------------- */}
          <View
            style={{
              flex: 1,
              backgroundColor: palette.surface,
              borderColor: palette.border,
              borderWidth: StyleSheet.hairlineWidth,
              borderRadius: 10,
            }}
          >
            <ScrollView
              style={{ flex: 1 }}
              contentContainerStyle={{ padding: 12 }}
            >
              {reply ? (
                <Text style={{ color: palette.text, fontSize: 15, lineHeight: 22 }}>
                  {reply}
                </Text>
              ) : (
                <Text style={[styles.cardMeta, { lineHeight: 18 }]}>
                  {streaming
                    ? "Waiting for the first chunk..."
                    : streamState === "done"
                    ? "(empty reply)"
                    : "The reply stream (SSE) will render here. Chat requires a session id \u2014 choose one above."}
                </Text>
              )}
            </ScrollView>
          </View>

          {/* --- raw SSE event log -------------------------------------- */}
          {eventLines.length > 0 ? (
            <View
              style={{
                marginTop: 8,
                maxHeight: 170,
                backgroundColor: "#0a0a0e",
                borderColor: palette.border,
                borderWidth: StyleSheet.hairlineWidth,
                borderRadius: 10,
                padding: 8,
              }}
            >
              <Text style={[styles.cardMeta, { marginBottom: 4 }]}>
                {"Raw SSE stream (" + eventLines.length + " events)"}
              </Text>
              <ScrollView style={{ maxHeight: 130 }}>
                <Text style={[styles.mono, { color: palette.textDim, fontSize: 11, lineHeight: 16 }]}>
                  {eventLines.join("\n")}
                </Text>
              </ScrollView>
            </View>
          ) : null}

          <ErrorNotice text={lastError} />

          {/* --- composer ------------------------------------------------ */}
          <View style={{ marginTop: 8 }}>
            <TextInput
              style={[styles.textArea, { minHeight: 66 }]}
              value={message}
              onChangeText={setMessage}
              placeholder={selected ? "Message " + selected.name + "..." : "Pick a session first"}
              placeholderTextColor={palette.textMuted}
              multiline
              editable={!streaming}
            />
            <View style={[styles.rowBetween, { marginTop: 8 }]}>
              <View style={styles.buttonRow}>
                <PrimaryButton
                  label={streaming ? "Sending..." : "Send"}
                  disabled={!canSend}
                  onPress={send}
                  small
                />
                {streaming ? (
                  <PrimaryButton label="Stop" secondary small onPress={stop} />
                ) : null}
              </View>
              <Pressable
                onPress={function () {
                  setUseStreaming(function (v) {
                    return !v;
                  });
                }}
                hitSlop={8}
              >
                <Text style={[styles.link, { fontSize: 12 }]}>
                  {useStreaming ? "SSE streaming: ON" : "POST /api/chat: ON"}
                </Text>
              </Pressable>
            </View>
          </View>
        </View>
      </KeyboardAvoidingView>

      {/* --- session picker modal -------------------------------------- */}
      <Modal
        visible={pickerOpen}
        transparent
        animationType="slide"
        onRequestClose={function () {
          setPickerOpen(false);
        }}
      >
        <Pressable
          style={{ flex: 1, backgroundColor: "rgba(0,0,0,0.6)", justifyContent: "center", padding: 20 }}
          onPress={function () {
            setPickerOpen(false);
          }}
        >
          <Pressable
            style={{ backgroundColor: palette.surface, borderRadius: 14, borderColor: palette.border, borderWidth: 1, maxHeight: "75%" }}
            onPress={function (e) {
              e.stopPropagation();
            }}
          >
            <View
              style={{
                flexDirection: "row",
                alignItems: "center",
                justifyContent: "space-between",
                padding: 14,
                borderBottomWidth: StyleSheet.hairlineWidth,
                borderBottomColor: palette.border,
              }}
            >
              <Text style={[styles.cardTitle, { fontSize: 16 }]}>Choose a session</Text>
              <Pressable onPress={function () { setPickerOpen(false); }} hitSlop={10}>
                <Text style={styles.link}>Close</Text>
              </Pressable>
            </View>
            <FlatList
              data={sessions}
              keyExtractor={function (s) {
                return s.id;
              }}
              style={{ maxHeight: 420 }}
              contentContainerStyle={{ padding: 8 }}
              renderItem={function ({ item }) {
                const active = selected && selected.id === item.id;
                return (
                  <Pressable
                    onPress={function () {
                      setSelected(item);
                      setPickerOpen(false);
                    }}
                    style={[
                      styles.card,
                      {
                        marginBottom: 6,
                        borderColor: active ? palette.accent : palette.border,
                      },
                    ]}
                  >
                    <View style={styles.rowBetween}>
                      <Text style={styles.cardTitle} numberOfLines={1}>
                        {item.name}
                      </Text>
                      {active ? (
                        <Text style={[styles.badgeText, { color: palette.accent }]}>selected</Text>
                      ) : null}
                    </View>
                    <Text style={styles.cardMeta} numberOfLines={1}>
                      {item.model ? item.model + " \u00b7 " : ""}id {item.id}
                      {item.folder ? " \u00b7 " + item.folder : ""}
                    </Text>
                  </Pressable>
                );
              }}
            />
          </Pressable>
        </Pressable>
      </Modal>
    </Screen>
  );
}
