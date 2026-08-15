import { environmentValue } from "./env";
import type { ApartmentPost, ScoreResult } from "./types";

export async function sendTelegramMatch(
  post: ApartmentPost,
  score: ScoreResult,
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
          text: telegramMessage(post, score),
          disable_web_page_preview: false,
        }),
      },
    );
    return response.ok ? "sent" : "error";
  } catch {
    return "error";
  }
}

function telegramMessage(post: ApartmentPost, score: ScoreResult): string {
  const lines = [
    `Apartment match: ${score.score}/100 (${score.decision})`,
    score.summary,
  ];
  if (post.groupName) lines.push(`Group: ${post.groupName}`);
  if (post.author) lines.push(`Posted by: ${post.author}`);
  if (score.priceIls) lines.push(`Price: ${score.priceIls} ILS`);
  lines.push(`Location: ${score.locationSignal}`);
  lines.push(`Protection: ${score.shelterSignal}`);
  if (score.positives.length) lines.push(`Good: ${score.positives.slice(0, 4).join("; ")}`);
  if (score.negatives.length) lines.push(`Watch: ${score.negatives.slice(0, 3).join("; ")}`);
  if (score.unknowns.length) lines.push(`?: ${score.unknowns.slice(0, 3).join("; ")}`);
  if (post.url) lines.push(post.url);
  return lines.join("\n");
}
