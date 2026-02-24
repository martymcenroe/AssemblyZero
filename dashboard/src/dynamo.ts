/**
 * DynamoDB client for CloudFlare Worker.
 *
 * Uses @aws-sdk/client-dynamodb with credentials from Worker secrets.
 */

import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient, QueryCommand } from "@aws-sdk/lib-dynamodb";

export type Env = {
  TABLE_NAME: string;
  AWS_REGION: string;
  AWS_ACCESS_KEY_ID: string;
  AWS_SECRET_ACCESS_KEY: string;
  API_KEY: string;
  GITHUB_CLIENT_ID: string;
  GITHUB_CLIENT_SECRET: string;
  JWT_SECRET: string;
  ALLOWED_GITHUB_USERNAME: string;
  ASSETS: Fetcher;
};

let cachedClient: DynamoDBDocumentClient | null = null;

function getClient(env: Env): DynamoDBDocumentClient {
  if (cachedClient) return cachedClient;

  const raw = new DynamoDBClient({
    region: env.AWS_REGION,
    credentials: {
      accessKeyId: env.AWS_ACCESS_KEY_ID,
      secretAccessKey: env.AWS_SECRET_ACCESS_KEY,
    },
  });

  cachedClient = DynamoDBDocumentClient.from(raw, {
    marshallOptions: { removeUndefinedValues: true },
  });

  return cachedClient;
}

/** Query events by repo (main table). */
export async function queryByRepo(
  env: Env,
  repo: string,
  limit = 50,
  lastKey?: Record<string, unknown>,
) {
  const client = getClient(env);
  const result = await client.send(
    new QueryCommand({
      TableName: env.TABLE_NAME,
      KeyConditionExpression: "pk = :pk",
      ExpressionAttributeValues: { ":pk": `REPO#${repo}` },
      ScanIndexForward: false,
      Limit: limit,
      ExclusiveStartKey: lastKey as any,
    }),
  );
  return { items: result.Items ?? [], lastKey: result.LastEvaluatedKey };
}

/** Query events by actor (GSI1). */
export async function queryByActor(
  env: Env,
  actor: string,
  limit = 50,
  lastKey?: Record<string, unknown>,
) {
  const client = getClient(env);
  const result = await client.send(
    new QueryCommand({
      TableName: env.TABLE_NAME,
      IndexName: "gsi1-actor-index",
      KeyConditionExpression: "gsi1pk = :pk",
      ExpressionAttributeValues: { ":pk": `ACTOR#${actor}` },
      ScanIndexForward: false,
      Limit: limit,
      ExclusiveStartKey: lastKey as any,
    }),
  );
  return { items: result.Items ?? [], lastKey: result.LastEvaluatedKey };
}

/** Query events by GitHub user (GSI2). */
export async function queryByUser(
  env: Env,
  user: string,
  limit = 50,
  lastKey?: Record<string, unknown>,
) {
  const client = getClient(env);
  const result = await client.send(
    new QueryCommand({
      TableName: env.TABLE_NAME,
      IndexName: "gsi2-user-index",
      KeyConditionExpression: "gsi2pk = :pk",
      ExpressionAttributeValues: { ":pk": `USER#${user}` },
      ScanIndexForward: false,
      Limit: limit,
      ExclusiveStartKey: lastKey as any,
    }),
  );
  return { items: result.Items ?? [], lastKey: result.LastEvaluatedKey };
}

/** Query events by date (GSI3). */
export async function queryByDate(
  env: Env,
  date: string,
  limit = 200,
  lastKey?: Record<string, unknown>,
) {
  const client = getClient(env);
  const result = await client.send(
    new QueryCommand({
      TableName: env.TABLE_NAME,
      IndexName: "gsi3-date-index",
      KeyConditionExpression: "gsi3pk = :pk",
      ExpressionAttributeValues: { ":pk": `DATE#${date}` },
      ScanIndexForward: false,
      Limit: limit,
      ExclusiveStartKey: lastKey as any,
    }),
  );
  return { items: result.Items ?? [], lastKey: result.LastEvaluatedKey };
}

/** Query error events from the last 7 days via GSI3 (date index). */
export async function queryErrors(env: Env, limit = 50) {
  const client = getClient(env);
  const errors: Record<string, unknown>[] = [];

  for (let i = 0; i < 7 && errors.length < limit; i++) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const dateStr = d.toISOString().slice(0, 10);

    const result = await client.send(
      new QueryCommand({
        TableName: env.TABLE_NAME,
        IndexName: "gsi3-date-index",
        KeyConditionExpression: "gsi3pk = :pk",
        ExpressionAttributeValues: { ":pk": `DATE#${dateStr}` },
        ScanIndexForward: false,
        Limit: 500,
      }),
    );

    for (const item of result.Items ?? []) {
      const et = item.event_type as string;
      if (et?.startsWith("error.") || et?.endsWith(".error")) {
        errors.push(item);
        if (errors.length >= limit) break;
      }
    }
  }

  return { items: errors };
}
