from pathlib import Path

# Finalize the generated application source.
main = Path("switch/source/main.cpp")
source = main.read_text()
declaration = "static bool g_apiSourceRefreshPending = false;"
if declaration not in source:
    marker = "static bool g_refreshRequested = false;\n"
    if source.count(marker) != 1:
        raise SystemExit("Could not locate controller refresh global")
    source = source.replace(marker, marker + declaration + "\n", 1)
main.write_text(source)

# The pinned Borealis TabFrame normally destroys a tab whenever the sidebar
# changes. That is wrong for our dynamically populated Home: returning to Home
# would recreate the XML placeholder and discard the cards. Add a tiny detach
# primitive and make TabFrame retain/re-attach its tab instances.
root = Path("switch/borealis")
box_h = root / "library/include/borealis/core/box.hpp"
box_cpp = root / "library/lib/core/box.cpp"
tab_h = root / "library/include/borealis/views/tab_frame.hpp"
tab_cpp = root / "library/lib/views/tab_frame.cpp"
for p in (box_h, box_cpp, tab_h, tab_cpp):
    if not p.exists():
        raise SystemExit(f"Missing Borealis source: {p}")

s = box_h.read_text()
if "void detachView(View* view);" not in s:
    marker = "    virtual void removeView(View* view);\n"
    if s.count(marker) != 1:
        raise SystemExit("Box removeView declaration not found")
    s = s.replace(marker, marker + "    void detachView(View* view);\n", 1)
    box_h.write_text(s)

s = box_cpp.read_text()
if "void Box::detachView(View* view)" not in s:
    marker = "void Box::removeView(View* view)\n"
    if s.count(marker) != 1:
        raise SystemExit("Box removeView definition not found")
    method = '''void Box::detachView(View* view)
{
    if (!view) return;
    size_t index = 0;
    bool found = false;
    for (size_t i = 0; i < this->children.size(); ++i)
    {
        if (this->children[i] == view) { index = i; found = true; break; }
    }
    if (!found) return;
    YGNodeRemoveChild(this->ygNode, view->getYGNode());
    this->children.erase(this->children.begin() + index);
    view->willDisappear(false);
    void* userdata = view->getParentUserData();
    view->setParent(nullptr, nullptr);
    std::free(userdata);
    this->invalidate();
}

'''
    s = s.replace(marker, method + marker, 1)
    box_cpp.write_text(s)

s = tab_h.read_text()
if "std::vector<View*> cachedTabs;" not in s:
    if "#include <vector>" not in s:
        s = s.replace("#include <functional>\n", "#include <functional>\n#include <vector>\n", 1)
    s = s.replace("    TabFrame();\n", "    TabFrame();\n    ~TabFrame() override;\n", 1)
    s = s.replace("    View* activeTab = nullptr;\n", "    View* activeTab = nullptr;\n    std::vector<View*> cachedTabs;\n    size_t activeTabIndex = 0;\n", 1)
    tab_h.write_text(s)

s = tab_cpp.read_text()
start = s.find("void TabFrame::addTab(std::string label, TabViewCreator creator)\n")
end = s.find("\nvoid TabFrame::addSeparator()", start)
if start < 0 or end < 0:
    raise SystemExit("TabFrame addTab boundaries not found")
add_tab = '''void TabFrame::addTab(std::string label, TabViewCreator creator)
{
    const size_t tabIndex = this->cachedTabs.size();
    this->cachedTabs.push_back(nullptr);
    this->sidebar->addItem(label, [this, creator, tabIndex](brls::View* view) {
        if (!view->isFocused()) return;
        Box* contentView = (Box*)this->contentView;
        if (!contentView) return;
        if (this->activeTab)
        {
            contentView->detachView(this->activeTab);
            this->activeTab = nullptr;
        }
        View* content = this->cachedTabs[tabIndex];
        if (!content)
        {
            content = creator();
            if (!content) return;
            content->setFocusable(true);
            this->cachedTabs[tabIndex] = content;
        }
        content->setGrow(1.0f);
        contentView->addView(content);
        this->activeTab = content;
        this->activeTabIndex = tabIndex;
        View* entry = content->getDefaultFocus();
        if (entry)
        {
            view->setCustomNavigationRoute(FocusDirection::RIGHT, entry);
            entry->setCustomNavigationRoute(FocusDirection::LEFT, view);
        }
        else
        {
            view->setCustomNavigationRoute(FocusDirection::RIGHT, content);
            content->setCustomNavigationRoute(FocusDirection::LEFT, view);
        }
    });
}
'''
s = s[:start] + add_tab + s[end:]

start = s.find("void TabFrame::setTabContent(View* content)\n")
if start < 0:
    marker = "void TabFrame::addSeparator()\n"
    pos = s.find(marker)
    if pos < 0: raise SystemExit("TabFrame addSeparator not found")
else:
    pos = start
    end = s.find("\nvoid TabFrame::addSeparator()", start)
    if end < 0: raise SystemExit("TabFrame setTabContent end not found")

set_block = '''void TabFrame::setTabContent(View* content)
{
    if (!content) return;
    Box* contentView = (Box*)this->contentView;
    if (!contentView) return;
    if (this->activeTab)
    {
        View* old = this->activeTab;
        contentView->detachView(old);
        this->activeTab = nullptr;
        if (this->activeTabIndex < this->cachedTabs.size() && this->cachedTabs[this->activeTabIndex] == old)
            this->cachedTabs[this->activeTabIndex] = nullptr;
        delete old;
    }
    content->setGrow(1.0f);
    contentView->addView(content);
    this->activeTab = content;
    if (this->activeTabIndex < this->cachedTabs.size())
        this->cachedTabs[this->activeTabIndex] = content;
}
'''
s = s[:pos] + set_block + s[(end if start >= 0 else pos):]

if "TabFrame::~TabFrame()" not in s:
    marker = "View* TabFrame::create()\n"
    if s.count(marker) != 1: raise SystemExit("TabFrame create definition not found")
    destructor = '''TabFrame::~TabFrame()
{
    for (size_t i = 0; i < this->cachedTabs.size(); ++i)
    {
        View* cached = this->cachedTabs[i];
        if (cached && cached != this->activeTab)
            delete cached;
    }
}

'''
    s = s.replace(marker, destructor + marker, 1)

tab_cpp.write_text(s)
print("Finalized API refresh globals and persistent TabFrame content")