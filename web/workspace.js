"use strict";
(() => {
  const path = (location.pathname.replace(/\/+$/, "") || "/");
  const pageNames = {
    "/": "研究工作台",
    "/dashboard3d.html": "全域三维专题",
    "/city.html": "两江立体图",
    "/district.html": "21 区县三维",
    "/data-center.html": "数据中心",
    "/guide.html": "毕设工作台",
    "/desktop.html": "桌面分析台",
    "/mobile.html": "口袋区县档案"
  };
  const make = (tag, className, text) => {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text != null) el.textContent = text;
    return el;
  };
  const routeItems = [
    ["/dashboard3d.html", "全域三维专题", "◫"],
    ["/city.html", "两江立体图", "⌖"],
    ["/district.html", "21 区县三维", "◎"]
  ];
  const projectItems = [
    ["/data-center.html", "数据中心", "▤"],
    ["/guide.html", "毕设工作台", "◇"]
  ];
  const toolItems = [
    ["/desktop.html", "桌面分析台"],
    ["/mobile.html", "口袋区县档案"]
  ];
  function makeLink(item) {
    const a = make("a", "workspace-link");
    a.href = item[0];
    a.title = item[1];
    if (path === item[0]) a.setAttribute("aria-current", "page");
    const icon = make("span", "workspace-link-icon", item[2] || "↗");
    icon.setAttribute("aria-hidden", "true");
    a.append(icon, make("span", "workspace-link-label", item[1]));
    return a;
  }
  function group(sidebar, label) {
    const section = make("section", "workspace-nav-group");
    section.append(make("div", "workspace-nav-heading", label));
    sidebar.append(section);
    return section;
  }
  function addRoutes(sidebar, label, items) {
    const section = group(sidebar, label);
    const list = make("div", "workspace-route-list");
    items.forEach(item => list.append(makeLink(item)));
    section.append(list);
  }
  function addTools(sidebar) {
    const details = make("details", "workspace-tools");
    const summary = make("summary", "", "更多工具");
    const list = make("div", "workspace-route-list");
    toolItems.forEach(item => list.append(makeLink(item)));
    details.append(summary, list);
    sidebar.append(details);
  }
  function closeSidebar() {
    document.body.classList.remove("workspace-nav-open");
    const toggle = document.querySelector(".workspace-menu-toggle");
    if (toggle) {
      toggle.setAttribute("aria-expanded", "false");
      toggle.setAttribute("aria-label", "打开主导航");
    }
  }
  function wireSidebar(sidebar) {
    if (!sidebar) return;
    sidebar.addEventListener("click", event => {
      const item = event.target.closest("a,button");
      if (item) closeSidebar();
    });
  }
  function addBackdrop() {
    const backdrop = make("button", "workspace-backdrop");
    backdrop.type = "button";
    backdrop.setAttribute("aria-label", "关闭导航");
    backdrop.addEventListener("click", closeSidebar);
    document.body.append(backdrop);
    return backdrop;
  }
  function addMobileToggle(actions) {
    const toggle = make("button", "workspace-menu-toggle", "☰");
    toggle.type = "button";
    toggle.setAttribute("aria-label", "打开主导航");
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-controls", "workspace-sidebar");
    toggle.addEventListener("click", () => {
      const open = document.body.classList.toggle("workspace-nav-open");
      toggle.setAttribute("aria-expanded", String(open));
      toggle.setAttribute("aria-label", open ? "关闭主导航" : "打开主导航");
    });
    actions.prepend(toggle);
    document.addEventListener("keydown", event => {
      if (event.key === "Escape") closeSidebar();
    });
  }
  function createSidebar(isHome, moduleNav) {
    const sidebar = make("aside", "workspace-sidebar");
    sidebar.id = "workspace-sidebar";
    sidebar.setAttribute("aria-label", "系统主导航");
    const brand = make("a", "workspace-brand");
    brand.href = "/";
    const logo = document.createElement("img");
    logo.src = "/icon192.png";
    logo.alt = "";
    const copy = make("span", "workspace-brand-copy");
    copy.append(make("strong", "", "山城地研"), make("small", "", "CHONGQING GEOINTELLIGENCE"));
    brand.append(logo, copy);
    sidebar.append(brand);
    if (isHome && moduleNav) {
      const section = group(sidebar, "研究工作台");
      moduleNav.classList.add("workspace-module-nav");
      moduleNav.setAttribute("aria-label", "研究工作台模块");
      moduleNav.querySelectorAll("button").forEach(button => { button.title = button.textContent.trim(); });
      section.append(moduleNav);
      addRoutes(sidebar, "空间探索", routeItems);
    } else {
      addRoutes(sidebar, "研究入口", [["/", "研究总览与分析", "⌂"]]);
      addRoutes(sidebar, "空间探索", routeItems);
    }
    addRoutes(sidebar, "数据与项目", projectItems);
    addTools(sidebar);
    const foot = make("div", "workspace-sidebar-foot");
    foot.append(make("strong", "", "21 区县研究范围"), make("span", "", "中心城区 9 区 · 主城新区 12 区"), make("small", "", "数据口径以已发布研究版本为准"));
    sidebar.append(foot);
    wireSidebar(sidebar);
    return sidebar;
  }
  function createTopbar(title, oldHeader, moduleNav, isHome) {
    const topbar = make("header", "workspace-topbar");
    const copy = make("div", "workspace-topbar-copy");
    const kicker = make("p", "workspace-topbar-kicker", "CHONGQING · LAND-USE INTELLIGENCE");
    const heading = make("h1", "workspace-page-title", title);
    heading.id = "workspace-page-title";
    const subtitle = make("p", "workspace-topbar-subtitle", isHome ? "重庆主城都市区 · 21 区县空间研究" : "山城地研 · 重庆主城都市区 21 区县研究平台");
    copy.append(kicker, heading, subtitle);
    const actions = make("div", "workspace-topbar-actions");
    if (oldHeader) {
      const buttons = Array.from(oldHeader.querySelectorAll("button")).filter(button => !moduleNav || !moduleNav.contains(button));
      buttons.forEach(button => actions.append(button));
    }
    addMobileToggle(actions);
    topbar.append(copy, actions);
    return { topbar, heading, subtitle };
  }
  function setupDesktop() {
    document.body.classList.add("app-desktop-page");
    const sidebar = document.querySelector("body > aside");
    const main = document.querySelector("body > main");
    if (sidebar) sidebar.classList.add("workspace-sidebar");
    if (main) {
      main.classList.add("workspace-desktop-main");
      main.id = main.id || "app-main-content";
      const header = main.querySelector(":scope > header");
      if (header) {
        header.classList.add("workspace-desktop-topbar");
        const actions = make("div", "workspace-desktop-actions");
        const toggle = make("button", "workspace-menu-toggle", "☰");
        toggle.type = "button";
        toggle.setAttribute("aria-label", "打开主导航");
        toggle.setAttribute("aria-expanded", "false");
        toggle.addEventListener("click", () => {
          const open = document.body.classList.toggle("workspace-nav-open");
          toggle.setAttribute("aria-expanded", String(open));
        });
        actions.append(toggle);
        header.append(actions);
      }
    }
    const nav = sidebar && sidebar.querySelector("nav");
    if (nav) {
      const current = make("a", "", "桌面分析台");
      current.href = "/desktop.html";
      current.setAttribute("aria-current", "page");
      current.title = "桌面分析台";
      nav.append(current);
      nav.querySelectorAll("button,a").forEach(item => { item.title = item.textContent.trim(); });
    }
    wireSidebar(sidebar);
    addBackdrop();
  }
  function setupMobile() {
    document.body.classList.add("app-mobile-page");
  }
  function setupShell() {
    const isHome = path === "/";
    const oldHeader = document.querySelector("body > header");
    const main = document.querySelector("body > main");
    const footer = document.querySelector("body > footer");
    if (!main) return;
    const moduleNav = isHome && oldHeader ? oldHeader.querySelector('nav[aria-label="主导航"]') : null;
    const fallbackTitle = main.querySelector("h1");
    const title = pageNames[path] || (oldHeader && oldHeader.querySelector("h1,h2") ? oldHeader.querySelector("h1,h2").textContent.trim() : fallbackTitle ? fallbackTitle.textContent.trim() : document.title);
    const sidebar = createSidebar(isHome, moduleNav);
    const { topbar, heading, subtitle } = createTopbar(title, oldHeader, moduleNav, isHome);
    const area = make("div", "workspace-main");
    const content = make("div", "workspace-content");
    main.id = main.id || "app-main-content";
    main.classList.add("workspace-page-content");
    const skip = make("a", "workspace-skip-link", "跳转到主内容");
    skip.href = "#" + main.id;
    const layout = make("div", "workspace-layout");
    const mainColumn = make("div", "workspace-main-column");
    content.append(main);
    if (footer) content.append(footer);
    mainColumn.append(topbar, content);
    layout.append(sidebar, mainColumn);
    document.body.classList.add("app-shell-page");
    document.body.dataset.appPage = path === "/" ? "home" : path.replace(/^\//, "").replace(/\.html$/, "");
    document.body.insertBefore(skip, document.body.firstChild);
    document.body.insertBefore(layout, skip.nextSibling);
    if (oldHeader) oldHeader.remove();
    addBackdrop();
    const titleSource = isHome ? document.getElementById("title") : path === "/district.html" ? document.getElementById("district-heading") : null;
    if (titleSource) {
      const observer = new MutationObserver(() => {
        if (isHome) subtitle.textContent = "当前模块 · " + titleSource.textContent.trim();
        else heading.textContent = titleSource.textContent.trim();
      });
      observer.observe(titleSource, { childList: true, characterData: true, subtree: true });
      if (isHome) subtitle.textContent = "当前模块 · " + titleSource.textContent.trim();
    }
  }
  if (path === "/mobile.html") setupMobile();
  else if (path === "/desktop.html") setupDesktop();
  else setupShell();
})();