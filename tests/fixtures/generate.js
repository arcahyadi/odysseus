/**
 * Générateur de fixtures réalistes pour les tests Odysseus.
 * Usage : node tests/fixtures/generate.js > tests/fixtures/test-data.json
 * Reproductible avec faker.seed(42)
 */
import { faker } from '@faker-js/faker';

// Seed pour reproductibilité
faker.seed(42);

const fixtures = {
  users: Array.from({ length: 10 }, () => ({
    id: faker.string.uuid(),
    email: faker.internet.email(),
    name: faker.person.fullName(),
    createdAt: faker.date.past().toISOString(),
  })),

  sessions: Array.from({ length: 5 }, () => ({
    id: faker.string.uuid(),
    userId: faker.string.uuid(),
    model: faker.helpers.arrayElement(['deepseek-v4-flash', 'kimi-k2.6', 'qwen3.7-plus']),
    tokensUsed: faker.number.int({ min: 100, max: 50000 }),
    costUsd: faker.number.float({ min: 0.01, max: 5.0, fractionDigits: 4 }),
    createdAt: faker.date.recent().toISOString(),
  })),

  memories: Array.from({ length: 20 }, () => ({
    id: faker.string.uuid(),
    content: faker.lorem.paragraph(),
    tags: faker.helpers.arrayElements(['coding', 'research', 'design', 'debug', 'planning'], 2),
    createdAt: faker.date.recent().toISOString(),
  })),
};

console.log(JSON.stringify(fixtures, null, 2));
