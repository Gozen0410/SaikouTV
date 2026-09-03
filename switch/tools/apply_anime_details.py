from pathlib import Path

path = Path("switch/source/main.cpp")
source = path.read_text()

if "SAIKOU_ANIME_DETAILS_V2" in source:
    print("Anime details click patch already installed")
    raise SystemExit(0)

old = '''        card->registerAction("Open anime", brls::BUTTON_A, [i](brls::View*) {
            char marker[64];
            std::snprintf(marker, sizeof(marker), "TRENDING CARD SELECTED %zu", i);
            log_stage(marker);
            return true;
        });'''

new = '''        card->registerAction("Open anime", brls::BUTTON_A, [i, titles, covers](brls::View*) {
            if (i >= titles.size())
                return false;

            g_selectedAnimeTitle = titles[i];
            g_selectedAnimeCover = i < covers.size() ? covers[i] : std::string();

            char marker[128];
            std::snprintf(marker, sizeof(marker), "TRENDING CARD OPEN DETAILS %zu", i);
            log_stage(marker);

            brls::Application::pushActivity(
                new AnimeDetailsActivity(g_selectedAnimeTitle, g_selectedAnimeCover),
                brls::TransitionAnimation::SLIDE_LEFT);
            return true;
        });'''

if old not in source:
    raise SystemExit("Could not locate pre-details Home card A action")

source = source.replace(old, new, 1)
source = source.replace("// SAIKOU_ANIME_DETAILS_V1: Home card -> anime details screen.", "// SAIKOU_ANIME_DETAILS_V1: Home card -> anime details screen.\n// SAIKOU_ANIME_DETAILS_V2: direct card activation opens the details Activity.", 1)
path.write_text(source)
print("Anime card A action wired directly to AnimeDetailsActivity")
