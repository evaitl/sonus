(function () {
  const playerBar = document.getElementById("player-bar");
  const audio = document.getElementById("global-player");
  const artEl = document.getElementById("player-art");
  const titleEl = document.getElementById("player-title");
  const artistEl = document.getElementById("player-artist");
  const defaultArtUrl = artEl ? artEl.dataset.defaultSrc || "" : "";

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
    } else {
      artEl.src = defaultArtUrl;
    }
    artEl.hidden = false;
    audio.src = track.streamUrl;
    audio.play().catch(() => {});
  }

  function shuffleArray(items) {
    const shuffled = items.slice();
    for (let i = shuffled.length - 1; i > 0; i -= 1) {
      const j = Math.floor(Math.random() * (i + 1));
      [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    return shuffled;
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
        let items = JSON.parse(button.dataset.playQueue || "[]");
        if (button.hasAttribute("data-shuffle")) {
          items = shuffleArray(items);
        }
        playQueue(items, 0);
      } catch (err) {
        console.error("Invalid playlist queue", err);
      }
    });
  });
})();
