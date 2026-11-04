// src/screens/PlansScreen.js
//
// GET /api/plans -> bare array of {id, title, goal, status, step_count,
// done_count, current_step_index, ...}. Tapping a plan loads the detail
// (GET /api/plans/{id}) which includes the steps array.
import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, FlatList, Pressable, Text, View } from "react-native";

import { Screen, ErrorNotice, LoadingBox, StatusChip } from "../components";
import { styles, palette } from "../styles";
import { listPlans, fetchPlan } from "../api/endpoints";
import { errMsg, excerpt } from "../utils";

export default function PlansScreen({ config, navigation }) {
  const { back, home } = navigation;
  const origin = config && config.origin ? config.origin : "";
  const token = config && config.token ? config.token : "";

  const [plans, setPlans] = useState(null);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [expandedId, setExpandedId] = useState(null);
  const [detail, setDetail] = useState(null); // { id, loading, error, steps: [] }

  const load = useCallback(
    async function (silent) {
      if (!silent) {
        setPlans(null);
      }
      setError("");
      try {
        const list = await listPlans(origin, token);
        setPlans(list);
      } catch (e) {
        setError(errMsg(e, "Could not load plans."));
        if (!silent) {
          setPlans([]);
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

  async function togglePlan(plan) {
    const id = plan.id;
    if (expandedId === id) {
      setExpandedId(null);
      setDetail(null);
      return;
    }
    setExpandedId(id);
    setDetail({ id: id, loading: true, error: "", steps: [] });
    try {
      const full = await fetchPlan(origin, token, id);
      setDetail({ id: id, loading: false, error: "", steps: full.steps || [] });
    } catch (e) {
      setDetail({ id: id, loading: false, error: errMsg(e, "Could not load steps."), steps: [] });
    }
  }

  function renderSteps(d) {
    if (!d) {
      return null;
    }
    return (
      <View style={{ marginTop: 8 }}>
        {d.loading ? (
          <View style={[styles.row, { marginTop: 4 }]}>
            <ActivityIndicator size="small" color={palette.accent} />
            <Text style={[styles.cardMeta, { marginLeft: 8 }]}>Loading steps...</Text>
          </View>
        ) : null}
        <ErrorNotice text={d.error} />
        {d.steps.length
          ? d.steps.map(function (step, index) {
              return (
                <View key={step.id || String(index)} style={styles.row}>
                  <Text style={[styles.mono, { color: palette.textMuted, fontSize: 12 }]}>
                    {index + 1}.
                  </Text>
                  <Text style={[styles.cardBody, { flex: 1, marginLeft: 8, color: palette.text }]}>
                    {excerpt(step.title, 120)}
                  </Text>
                  <StatusChip value={step.status || "pending"} />
                </View>
              );
            })
          : null}
      </View>
    );
  }

  return (
    <Screen title="Plans" onBack={back} onAction={home} actionLabel="Home">
      {plans === null ? (
        <LoadingBox text="Loading plans..." />
      ) : (
        <FlatList
          style={styles.flex1}
          data={plans}
          keyExtractor={function (p) {
            return p.id || String(Math.random());
          }}
          contentContainerStyle={styles.listContent}
          onRefresh={onRefresh}
          refreshing={refreshing}
          ListEmptyComponent={
            <View style={styles.center}>
              <Text style={styles.centerText}>
                {error ? "Could not load plans." : "No plans yet on this server."}
              </Text>
            </View>
          }
          renderItem={function ({ item }) {
            const expanded = expandedId === item.id;
            const progress =
              item.step_count > 0
                ? item.done_count + "/" + item.step_count + " steps done"
                : "no steps";
            const running =
              ["in_progress", "in-progress", "active", "running"].indexOf(
                String(item.status || "").toLowerCase()
              ) !== -1;
            return (
              <Pressable
                onPress={function () {
                  togglePlan(item);
                }}
                style={({ pressed }) => [
                  styles.card,
                  pressed ? { backgroundColor: palette.surfaceAlt } : null,
                ]}
              >
                <View style={styles.rowBetween}>
                  <Text style={[styles.cardTitle, { flex: 1, marginRight: 8 }]}>
                    {excerpt(item.title || "(untitled)", 90)}
                  </Text>
                  <StatusChip value={item.status || "unknown"} />
                </View>
                {item.goal ? (
                  <Text style={styles.cardBody} numberOfLines={2}>
                    {excerpt(item.goal, 160)}
                  </Text>
                ) : null}
                <Text style={styles.cardMeta}>
                  {progress}
                  {running && typeof item.current_step_index === "number"
                    ? " \u00b7 on step " + (item.current_step_index + 1)
                    : ""}
                </Text>
                {expanded ? renderSteps(detail) : null}
              </Pressable>
            );
          }}
        />
      )}
      <ErrorNotice text={plans === null ? "" : error} />
    </Screen>
  );
}
