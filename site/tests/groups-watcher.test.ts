import assert from "node:assert/strict";
import test from "node:test";
import { postsFromPayload } from "../lib/groups-watcher";

test("normalizes the Groups Watcher 5.13 extension payload", () => {
  const posts = postsFromPayload({
    message: "New FB Post Detected",
    data: {
      group_url: "https://www.facebook.com/groups/982821351800566/",
      group_id: "982821351800566",
      profile_url: "https://www.facebook.com/carlosrosmaninhog90",
      profile_name: "Carlos Rosmaninho",
      post_url:
        "https://www.facebook.com/groups/982821351800566/posts/8787558701326753/",
      post_text: "MOCK REQUEST",
      time_posted: "12/3/2024, 4:50:59 PM",
    },
  });

  assert.equal(posts.length, 1);
  assert.equal(posts[0].source, "groups-watcher:982821351800566");
  assert.equal(posts[0].text, "MOCK REQUEST");
  assert.equal(posts[0].author, "Carlos Rosmaninho");
  assert.equal(
    posts[0].url,
    "https://www.facebook.com/groups/982821351800566/posts/8787558701326753/",
  );
  assert.equal(posts[0].postedAt, "12/3/2024, 4:50:59 PM");
});

test("keeps supporting the managed Groups Watcher payload", () => {
  const posts = postsFromPayload({
    data: {
      group_name: "Tel Aviv Apartments",
      poster_name: "Dana",
      body: "Montefiore room, 3800 ILS",
      timestamp: "2026-08-15T10:00:00Z",
    },
  });

  assert.equal(posts[0].source, "groups-watcher:Tel Aviv Apartments");
  assert.equal(posts[0].text, "Montefiore room, 3800 ILS");
  assert.equal(posts[0].author, "Dana");
});
