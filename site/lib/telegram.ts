import { environmentValue } from "./env";
import type { AnalysisResult, ApartmentPost } from "./types";

export async function sendTelegramMatch(
  post: ApartmentPost,
  result: AnalysisResult,
): Promise<"sent" | "disabled" | "error"> {
  const token = environmentValue("TELEGRAM_BOT_TOKEN");
  const chatId = environmentValue("TELEGRAM_CHAT_ID");
  if (!token || !chatId) return "disabled";

  try {
    const response = await fetch(
      `https://api.telegram.org/bot${encodeURIComponent(token)}/sendMessage`,
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          chat_id: chatId,
          text: telegramMessage(post, result),
          disable_web_page_preview: false,
        }),
      },
    );
    return response.ok ? "sent" : "error";
  } catch {
    return "error";
  }
}

function telegramMessage(post: ApartmentPost, result: AnalysisResult): string {
  const lines = [
    `Apartment match: ${result.score}/100 (Recommended)`,
    result.summary,
  ];
  if (post.groupName) lines.push(`Group: ${post.groupName}`);
  if (post.author) lines.push(`Posted by: ${post.author}`);
  if (result.priceIls) lines.push(`Price: ${result.priceIls} ILS`);
  lines.push(`Location: ${result.locationSignal}`);
  if (result.walkToWorkMinutes !== null) {
    lines.push(`Walk to HaHaskala 3: ${result.walkToWorkMinutes} min`);
  }
  if (result.walkToSaronaMinutes !== null) {
    lines.push(`Walk to Sarona: ${result.walkToSaronaMinutes} min`);
  }
  lines.push(`Protection: ${result.shelterSignal}`);
  if (result.positives.length) lines.push(`Good: ${result.positives.slice(0, 4).join("; ")}`);
  if (result.concerns.length) lines.push(`Watch: ${result.concerns.slice(0, 3).join("; ")}`);
  if (result.unknowns.length) lines.push(`?: ${result.unknowns.slice(0, 3).join("; ")}`);
  if (post.url) lines.push(post.url);
  return lines.join("\n");
}
