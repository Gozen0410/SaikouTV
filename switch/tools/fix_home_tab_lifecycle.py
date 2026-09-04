from pathlib import Path

# The workflow runs this script from switch/, after cloning the pinned
# Borealis checkout into switch/borealis.
root = Path("borealis")
tab_h = root / "library/include/borealis/views/tab_frame.hpp"
tab_cpp = root / "library/lib/views/tab_frame.cpp"

for p in (tab_h, tab_cpp):
    if not p.exists():
        raise SystemExit(f"Missing Borealis source: {p}")

# Keep Borealis' normal TabFrame behavior for every tab except Home. Home is
# dynamically populated after its first request, so destroying it on every
# sidebar change loses the cards. Switchfin solves this by retaining the tab's
# attached View and re-attaching it when the tab becomes active.
s = tab_h.read_text()
if "View* cachedHomeTab = nullptr;" not in s:
    marker = "    View* activeTab = nullptr;\n"
    if s.count(marker) != 1:
        raise SystemExit("TabFrame activeTab member not found")
    s = s.replace(marker, marker + "    View* cachedHomeTab = nullptr;\n", 1)
if "~TabFrame() override;" not in s:
    marker = "    TabFrame();\n"
    if s.count(marker) != 1:
        raise SystemExit("TabFrame constructor declaration not found")
    s = s.replace(marker, marker + "    ~TabFrame() override;\n", 1)
tab_h.write_text(s)

s = tab_cpp.read_text()
start = s.find("void TabFrame::addTab(std::string label, TabViewCreator creator)\n")
if start < 0:
    raise SystemExit("TabFrame addTab definition not found")
# Patch Borealis injects setTabContent() before addSeparator(). Preserve it
# instead of accidentally deleting it while replacing addTab().
content_marker = s.find("\nvoid TabFrame::setTabContent(View* content)\n", start)
separator_marker = s.find("\nvoid TabFrame::addSeparator()", start)
if content_marker >= 0:
    end = content_marker
elif separator_marker >= 0:
    end = separator_marker
else:
    raise SystemExit("TabFrame addTab boundaries not found")

# Home is the first tab in Saikou's TabFrame. Capture that fact when the tab is
# registered so localization cannot break the persistence rule.
is_home = "this->sidebar->getChildren().empty()"
add_tab = f'''void TabFrame::addTab(std::string label, TabViewCreator creator)
{{
    const bool isHomeTab = {is_home};
    this->sidebar->addItem(label, [this, creator, isHomeTab](brls::View* view) {{
        if (!view->isFocused())
            return;

        Box* contentView = (Box*)this->contentView;
        if (!contentView)
            return;

        if (this->activeTab)
        {{
            // The stock removeView(view) deletes the tab. For Home, retain the
            // View and let the next Home activation re-attach it.
            if (this->activeTab == this->cachedHomeTab)
                contentView->removeView(this->activeTab, false);
            else
                contentView->removeView(this->activeTab);
            this->activeTab = nullptr;
        }}

        View* newContent = nullptr;
        if (isHomeTab && this->cachedHomeTab)
            newContent = this->cachedHomeTab;
        else
            newContent = creator();

        if (!newContent)
            return;

        if (isHomeTab)
            this->cachedHomeTab = newContent;

        newContent->setFocusable(true);
        view->setCustomNavigationRoute(FocusDirection::RIGHT, newContent);
        newContent->setCustomNavigationRoute(FocusDirection::LEFT, view);
        newContent->setGrow(1.0f);
        contentView->addView(newContent);
        this->activeTab = newContent;
    }});
}}
'''
s = s[:start] + add_tab + s[end:]

# setTabContent() was injected by Patch Borealis before this script. It is used
# by the Home loader to replace the placeholder with dynamically generated
# cards. Replace that implementation without changing its location.
start = s.find("void TabFrame::setTabContent(View* content)\n")
if start < 0:
    raise SystemExit("TabFrame setTabContent was not injected by workflow")
end = s.find("\nvoid TabFrame::addSeparator()", start)
if end < 0:
    raise SystemExit("TabFrame setTabContent end not found")

set_block = '''void TabFrame::setTabContent(View* content)
{
    if (!content)
        return;

    Box* contentView = (Box*)this->contentView;
    if (!contentView)
        return;

    if (this->activeTab)
    {
        View* old = this->activeTab;
        if (old == this->cachedHomeTab)
        {
            contentView->removeView(old, false);
            delete old;
        }
        else
        {
            contentView->removeView(old);
        }
        this->activeTab = nullptr;
    }

    content->setFocusable(true);
    content->setGrow(1.0f);
    contentView->addView(content);
    this->activeTab = content;
    this->cachedHomeTab = content;
}
'''
s = s[:start] + set_block + s[end:]

# Inactive cached Home is not a child of TabFrame, so clean it up here. The
# active Home remains a child and is destroyed by the normal base destructor.
if "TabFrame::~TabFrame()" not in s:
    marker = "View* TabFrame::create()\n"
    if s.count(marker) != 1:
        raise SystemExit("TabFrame create definition not found")
    destructor = '''TabFrame::~TabFrame()
{
    if (this->cachedHomeTab && this->cachedHomeTab != this->activeTab)
        delete this->cachedHomeTab;
}

'''
    s = s.replace(marker, destructor + marker, 1)

tab_cpp.write_text(s)
print("Installed minimal Home-only TabFrame retention using Borealis removeView(view, false)")
