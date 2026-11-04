// src/components.js
//
// Tiny shared UI pieces (JSX). Everything else is per-screen inline style from
// src/styles.js. No third-party UI dependencies.
import React from "react";
import { ActivityIndicator, Pressable, Text, View } from "react-native";

import { styles, statusColor } from "./styles";
import { humanStatus } from "./utils";

// Standard screen chrome: title bar with optional Back (left) and an action
// link (right), then the screen body.
export function Screen({ title, onBack, onAction, actionLabel, children }) {
  return (
    <View style={styles.screen}>
      <View style={styles.header}>
        <View style={styles.headerSide}>
          {onBack ? (
            <Pressable onPress={onBack} hitSlop={10}>
              <Text style={styles.link}>{"\u2039 Back"}</Text>
            </Pressable>
          ) : null}
        </View>
        <Text style={styles.headerTitle} numberOfLines={1}>
          {title}
        </Text>
        <View style={[styles.headerSide, { alignItems: "flex-end" }]}>
          {onAction ? (
            <Pressable onPress={onAction} hitSlop={10}>
              <Text style={styles.link}>{actionLabel || "Action"}</Text>
            </Pressable>
          ) : null}
        </View>
      </View>
      <View style={styles.flex1}>{children}</View>
    </View>
  );
}

// Centred spinner for initial loads.
export function LoadingBox({ text }) {
  return (
    <View style={styles.center}>
      <ActivityIndicator color={styles ? "#7c9cff" : undefined} size="large" />
      <Text style={styles.centerText}>{text || "Loading..."}</Text>
    </View>
  );
}

// Red error banner.
export function ErrorNotice({ text }) {
  if (!text) {
    return null;
  }
  return (
    <View style={[styles.notice, styles.noticeError]}>
      <Text style={styles.noticeText}>{text}</Text>
    </View>
  );
}

// Coloured info banner. tone: "ok" | "warn" | "info" | "error"
export function Notice({ text, tone }) {
  if (!text) {
    return null;
  }
  const toneStyle =
    tone === "ok"
      ? styles.noticeOk
      : tone === "warn"
      ? styles.noticeWarn
      : tone === "info"
      ? styles.noticeInfo
      : styles.noticeError;
  return (
    <View style={[styles.notice, toneStyle]}>
      <Text style={styles.noticeText}>{text}</Text>
    </View>
  );
}

// Pill that colour-codes a status string (done/failed/paused/...).
export function StatusChip({ value }) {
  const color = statusColor(value);
  return (
    <View style={[styles.badge, { borderColor: color }]}>
      <Text style={[styles.badgeText, { color: color }]}>{humanStatus(value)}</Text>
    </View>
  );
}

// Primary / secondary button.
export function PrimaryButton({ label, onPress, disabled, secondary, small }) {
  return (
    <Pressable
      disabled={disabled || false}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        secondary ? styles.buttonSecondary : null,
        small ? styles.buttonSmall : null,
        disabled ? styles.buttonDisabled : null,
        pressed && !disabled ? { opacity: 0.85 } : null,
      ]}
    >
      <Text
        style={[
          styles.buttonText,
          secondary ? styles.buttonSecondaryText : null,
          small ? styles.small : null,
        ]}
      >
        {label}
      </Text>
    </Pressable>
  );
}
