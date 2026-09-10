import React from "react";
import { useLocalSearchParams } from "expo-router";
import { PublicActivityChat } from "../src/PublicActivityChat";
import { StockConversations } from "../src/StockConversations";

export default function Chat() {
  const { activity_id } = useLocalSearchParams<{ activity_id?: string | string[] }>();
  return activity_id ? <PublicActivityChat /> : <StockConversations />;
}
