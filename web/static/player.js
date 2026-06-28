(function () {
  const playerBar = document.getElementById("player-bar");
  const audio = document.getElementById("global-player");
  const artEl = document.getElementById("player-art");
  const titleEl = document.getElementById("player-title");
  const artistEl = document.getElementById("player-artist");

  if (!audio || !playerBar) {
    return;
  }

  let queue = [];
  let queueIndex = 0;

  function showPlayer(track) {
    playerBar.hidden = false;
    document.body.classList.add("has-player");
    titleEl.textContent = track.title || "Unknown track";
    artistEl.textContent = track.artist || "";
    if (track.artUrl) {
      artEl.src = track.artUrl;
      artEl.hidden = false;
    } else {
      artEl.removeAttribute("src");
      artEl.hidden = true;
    }
    audio.src = track.streamUrl;
    audio.play().catch(() => {});
  }

  function playQueue(items, startIndex) {
    queue = items;
    queueIndex = startIndex || 0;
    if (!queue.length) {
      return;
    }
    showPlayer(queue[queueIndex]);
  }

  audio.addEventListener("ended", () => {
    if (queueIndex + 1 < queue.length) {
      queueIndex += 1;
      showPlayer(queue[queueIndex]);
    }
  });

  document.querySelectorAll("[data-play-track]").forEach((button) => {
    button.addEventListener("click", () => {
      playQueue(
        [
          {
            streamUrl: button.dataset.streamUrl,
            title: button.dataset.title,
            artist: button.dataset.artist,
            artUrl: button.dataset.artUrl,
          },
        ],
        0
      );
    });
  });

  document.querySelectorAll("[data-play-queue]").forEach((button) => {
    button.addEventListener("click", () => {
      try {
        const items = JSON.parse(button.dataset.playQueue || "[]");
        playQueue(items, 0);
      } catch (err) {
        console.error("Invalid playlist queue", err);
      }
    });
  });
})();
