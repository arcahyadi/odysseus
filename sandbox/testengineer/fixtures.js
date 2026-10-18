/**
 * Faker.js fixtures for AgentOS TestEngineer sandbox.
 *
 * Seedable (`faker.seed(42)`) → deterministic, reproducible test data.
 * Generates realistic mock data for E2E tests, demos, and agent QA.
 *
 * Usage:
 *   import { faker, seed } from './fixtures.js';
 *   seed(42);  // reproducible
 *   const user = fakeUser();
 *
 * Requires: npm i -D @faker-js/faker
 */

import { faker } from '@faker-js/faker';

// ── Seed control ────────────────────────────────────────────────────
export function seed(n = 42) {
  faker.seed(n);
}

// ── User fixtures ───────────────────────────────────────────────────
export function fakeUser() {
  return {
    id: faker.string.uuid(),
    name: faker.person.fullName(),
    email: faker.internet.email(),
    avatar: faker.image.avatar(),
    bio: faker.lorem.sentence(),
    createdAt: faker.date.past().toISOString(),
  };
}

export function fakeUsers(n = 5) {
  return Array.from({ length: n }, () => fakeUser());
}

// ── Project fixtures ────────────────────────────────────────────────
export function fakeProject() {
  return {
    id: faker.string.uuid(),
    name: faker.company.name(),
    description: faker.lorem.paragraph(),
    language: faker.helpers.arrayElement(['Python', 'TypeScript', 'Rust', 'Go', 'Java']),
    stars: faker.number.int({ min: 0, max: 50000 }),
    createdAt: faker.date.past().toISOString(),
  };
}

// ── Commit fixtures ─────────────────────────────────────────────────
export function fakeCommit(projectId) {
  return {
    hash: faker.git.shortSha(),
    message: faker.git.commitMessage(),
    author: faker.person.fullName(),
    projectId: projectId || faker.string.uuid(),
    timestamp: faker.date.recent().toISOString(),
  };
}

// ── Task / Issue fixtures ───────────────────────────────────────────
export function fakeTask(projectId) {
  return {
    id: faker.string.uuid(),
    title: faker.hacker.phrase(),
    description: faker.lorem.paragraphs(2),
    priority: faker.helpers.arrayElement(['low', 'medium', 'high', 'critical']),
    status: faker.helpers.arrayElement(['todo', 'in_progress', 'review', 'done']),
    projectId: projectId || faker.string.uuid(),
    createdAt: faker.date.recent().toISOString(),
  };
}

// ── API response fixtures ───────────────────────────────────────────
export function fakeApiResponse(data, ok = true) {
  return {
    ok,
    status: ok ? 200 : faker.helpers.arrayElement([400, 404, 500]),
    data,
    timestamp: new Date().toISOString(),
  };
}

// ── File fixtures ───────────────────────────────────────────────────
export function fakeFilePath() {
  return faker.system.filePath();
}

export function fakeFileContent(lines = 20) {
  return Array.from({ length: lines }, () => faker.lorem.sentence()).join('\n');
}

// ── Database row fixtures ───────────────────────────────────────────
export function fakeDbRow(table, overrides = {}) {
  const base = {
    id: faker.string.uuid(),
    created_at: faker.date.past().toISOString(),
    updated_at: faker.date.recent().toISOString(),
  };
  if (table === 'users') return { ...base, ...fakeUser(), ...overrides };
  if (table === 'projects') return { ...base, ...fakeProject(), ...overrides };
  return { ...base, ...overrides };
}

export { faker };
