// Shared palette + stylesheet for every screen. Plain RN StyleSheet (no JSX).
import { Platform, StyleSheet } from "react-native";

export const palette = {
  bg: "#0e0e12",
  surface: "#1a1a21",
  surfaceAlt: "#24242e",
  border: "#2e2e3a",
  text: "#e9e9ee",
  textDim: "#9d9dab",
  textMuted: "#5f5f6b",
  accent: "#7c9cff",
  accentSoft: "#232c4d",
  onAccent: "#0d0f17",
  ok: "#7ec699",
  warn: "#e0a85e",
  danger: "#e06c75",
};

// Colour hint for status strings ("done", "failed", "paused", ...). Unknown
// values fall back to a dim neutral tone.
export function statusColor(value) {
  const s = String(value == null ? "" : value).toLowerCase();
  if (["done", "complete", "completed", "success", "succeeded", "ok", "finished"].includes(s)) {
    return palette.ok;
  }
  if (["failed", "error", "cancelled", "canceled", "stopped"].includes(s)) {
    return palette.danger;
  }
  if (["paused", "pending", "queued", "waiting", "blocked", "running", "in_progress", "in-progress", "active", "inactive"].includes(s)) {
    return palette.warn;
  }
  return palette.textDim;
}

export const styles = StyleSheet.create({
  flex1: { flex: 1 },

  screen: {
    flex: 1,
    backgroundColor: palette.bg,
    paddingTop: Platform.OS === "ios" ? 52 : 30,
  },

  // -- Header -------------------------------------------------------------
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: palette.border,
    backgroundColor: palette.surface,
  },
  headerTitle: {
    flex: 1,
    textAlign: "center",
    color: palette.text,
    fontSize: 17,
    fontWeight: "700",
  },
  headerSide: {
    width: 74,
  },
  link: {
    color: palette.accent,
    fontSize: 15,
    fontWeight: "600",
  },

  content: {
    padding: 14,
  },

  // -- Cards --------------------------------------------------------------
  card: {
    backgroundColor: palette.surface,
    borderColor: palette.border,
    borderWidth: StyleSheet.hairlineWidth,
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
  },
  cardTitle: {
    color: palette.text,
    fontSize: 15,
    fontWeight: "700",
  },
  cardMeta: {
    color: palette.textDim,
    fontSize: 12,
    marginTop: 2,
  },
  cardBody: {
    color: palette.textDim,
    fontSize: 13,
    lineHeight: 19,
    marginTop: 6,
  },

  row: {
    flexDirection: "row",
    alignItems: "center",
  },
  rowBetween: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },

  badge: {
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 8,
    paddingVertical: 2,
    alignSelf: "flex-start",
  },
  badgeText: {
    fontSize: 11,
    fontWeight: "700",
    textTransform: "capitalize",
  },

  divider: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: palette.border,
    marginVertical: 10,
  },

  // -- Form fields ---------------------------------------------------------
  field: {
    marginBottom: 12,
  },
  inputLabel: {
    color: palette.textDim,
    fontSize: 12,
    fontWeight: "600",
    marginBottom: 6,
    textTransform: "uppercase",
    letterSpacing: 0.4,
  },
  input: {
    backgroundColor: palette.surfaceAlt,
    borderColor: palette.border,
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: Platform.OS === "ios" ? 12 : 8,
    color: palette.text,
    fontSize: 15,
  },
  textArea: {
    backgroundColor: palette.surfaceAlt,
    borderColor: palette.border,
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: palette.text,
    fontSize: 14,
    minHeight: 84,
    textAlignVertical: "top",
  },

  // -- Buttons -------------------------------------------------------------
  buttonRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  button: {
    backgroundColor: palette.accent,
    borderRadius: 10,
    paddingHorizontal: 18,
    paddingVertical: 12,
    alignItems: "center",
  },
  buttonSecondary: {
    backgroundColor: palette.surfaceAlt,
    borderColor: palette.border,
    borderWidth: 1,
  },
  buttonSmall: {
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  buttonDisabled: {
    opacity: 0.45,
  },
  buttonText: {
    color: palette.onAccent,
    fontSize: 15,
    fontWeight: "700",
  },
  buttonSecondaryText: {
    color: palette.text,
  },

  // -- Notices --------------------------------------------------------------
  notice: {
    borderRadius: 10,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginBottom: 12,
  },
  noticeError: {
    backgroundColor: "#2a171b",
    borderColor: palette.danger,
  },
  noticeOk: {
    backgroundColor: "#12251c",
    borderColor: palette.ok,
  },
  noticeWarn: {
    backgroundColor: "#2a2015",
    borderColor: palette.warn,
  },
  noticeInfo: {
    backgroundColor: palette.accentSoft,
    borderColor: palette.accent,
  },
  noticeText: {
    color: palette.text,
    fontSize: 13,
    lineHeight: 18,
  },

  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
  },
  centerText: {
    color: palette.textDim,
    fontSize: 14,
    textAlign: "center",
    lineHeight: 20,
    marginTop: 10,
  },

  small: {
    fontSize: 12,
  },
  mono: {
    fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace",
  },
  muted: {
    color: palette.textMuted,
  },

  listContent: {
    padding: 14,
    paddingBottom: 48,
  },
});
