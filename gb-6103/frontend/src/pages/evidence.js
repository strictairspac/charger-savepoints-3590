import { api } from "../api/workbench.js";
import { errorText, field } from "../components/common/fields.js";
import { empty, pageHeading, section } from "../components/common/panel.js";
import { resultTable } from "../components/common/table.js";
import { ClearanceStates } from "../constants/states.js";
import { submit } from "../hooks/submit.js";
import { el } from "../utils/dom.js";
import { cell, download, time } from "../utils/format.js";

function reviewForm(id, saved) {
  const form = el("form", {id: "review-form"},
    field("复核意见", el("textarea", {name: "note", required: true, minlength: 3, maxlength: 500, rows: 3})),
    errorText(), el("button", {type: "submit"}, "签署复核"));
  submit(form, async values => saved(await api.submitReview(id, {note: values.get("note")})));
  return form;
}

function signature(review) {
  return el("div", {"data-testid": "reviewed", class: "signature"},
    el("strong", {}, `已签署 · ${review.actor}`), el("p", {}, review.note), el("time", {}, time(review.created_at)));
}

function revocationForm(saved) {
  const form = el("form", {id: "revocation-form"},
    field("撤销单编号", el("input", {name: "code", maxlength: 32, placeholder: "留空自动编号"})),
    field("仪表号", el("input", {name: "meter", required: true, maxlength: 24})),
    field("失效开始", el("input", {name: "invalid_from", type: "datetime-local", required: true})),
    field("失效结束", el("input", {name: "invalid_to", type: "datetime-local", required: true})),
    field("说明", el("input", {name: "note", maxlength: 500})),
    errorText(), el("button", {type: "submit"}, "登记撤销单"));
  submit(form, async values => {
    // datetime-local has no zone; send the wall clock as-is so the backend
    // reads it in China Standard Time instead of the browser's local zone.
    const stamp = name => (values.get(name) || "").replace("T", " ");
    saved(await api.registerRevocation({
      code: values.get("code").trim() || null,
      meter: values.get("meter").trim(),
      invalid_from: stamp("invalid_from"),
      invalid_to: stamp("invalid_to"),
      note: values.get("note"),
    }));
  });
  return form;
}

function stateLabel(state, config) {
  return config?.clearance_states?.[state] || ClearanceStates[state] || state;
}

function stateChip(state, config) {
  return el("span", {class: "status clearance-state", "data-clearance": state}, stateLabel(state, config));
}

function revokedPorts(station) {
  const touched = station.ports.filter(port => port.invalid);
  return touched.length ? touched.map(port => port.port_serial).join("、") : "—";
}

function stationDetail(station, config) {
  const rows = station.ports.map(port => [
    port.port_serial, port.meter, time(port.tested_at),
    `${port.insulation} kΩ`, port.interlock ? "通过" : "未通过",
    port.revocations.length ? port.revocations.join("、") : "—",
    port.retest ? `${port.retest.tested_text} · ${port.retest.insulation} kΩ` : "—",
    stateChip(port.state, config),
  ]);
  return el("details", {open: station.state === "停送"},
    el("summary", {}, `${station.station} · ${station.district} · ${stateLabel(station.state, config)}`),
    el("p", {}, station.basis),
    el("div", {class: "table-scroll", tabindex: 0, role: "region", "aria-label": `${station.station} 枪口核对`},
      el("table", {},
        el("thead", {}, el("tr", {}, ["枪口", "仪表号", "检测时间", "读数", "联锁", "撤销单", "复测", "结论"]
          .map(text => el("th", {scope: "col"}, text)))),
        el("tbody", {}, rows.map(row => el("tr", {}, row.map(value => el("td", {}, value instanceof Node ? value : cell(value)))))))));
}

function clearanceView(live, config) {
  const involved = live.revocations;
  return el("div", {class: "stack", "data-testid": "clearance"},
    el("div", {class: "clearance-head"},
      stateChip(live.judgment, config),
      el("strong", {}, live.releasable ? "全部通过站点均可送电" :
        live.judgment === "无检测台账" ? "无检测台账，不能签署" :
        live.signable ? "部分站点停送待复测，可签署并记录分站判定" : "全部通过站点停送待复测，不能签署")),
    el("h3", {}, "涉及撤销单"),
    involved.length ? el("ul", {class: "plain"}, involved.map(item =>
      el("li", {}, `${item.code} · 仪表 ${item.meter} · 失效 ${item.invalid_text}`))) :
      el("p", {class: "empty"}, "本批次没有枪口落入已登记的撤销单失效时段。"),
    el("h3", {}, "停送或恢复送电的依据"),
    el("ul", {"data-testid": "clearance-basis", class: "plain"}, live.basis.map(line => el("li", {}, line))),
    section("涉及枪口", live.stations.some(item => item.involved.length) ?
      el("div", {class: "table-scroll", tabindex: 0, role: "region", "aria-label": "涉及撤销单的枪口"},
        el("table", {},
          el("thead", {}, el("tr", {}, ["站号", "片区", "涉及枪口", "原判定", "当前结论", "依据"]
            .map(text => el("th", {scope: "col"}, text)))),
          el("tbody", {}, live.stations.map(item => el("tr", {},
            [item.station, item.district, revokedPorts(item), item.original, stateChip(item.state, config), item.basis]
              .map(value => el("td", {}, value instanceof Node ? value : cell(value)))))))) :
      empty("没有枪口涉及撤销单。")),
    el("h3", {}, "分站核对"),
    live.stations.map(station => stationDetail(station, config)));
}

function signedView(signed, config) {
  const snapshot = signed.snapshot;
  return el("div", {class: "stack", "data-testid": "signed-clearance"},
    el("p", {}, "已签核对单按签署时的判定保留，后续撤销单不覆盖本单。"),
    signature(signed),
    snapshot ? el("div", {class: "stack"},
      el("p", {}, `签署时判定：${stateLabel(snapshot.judgment, config)}`),
      el("ul", {class: "plain"}, snapshot.basis.map(line => el("li", {}, line))),
      snapshot.stations?.length ? el("div", {class: "table-scroll", tabindex: 0, role: "region", "aria-label": "签署时枪口判定"},
        el("table", {},
          el("thead", {}, el("tr", {}, ["站号", "涉及枪口", "签署时结论"].map(text => el("th", {scope: "col"}, text)))),
          el("tbody", {}, snapshot.stations.map(item => el("tr", {},
            [item.station, item.involved.join("、") || "—", stateChip(item.state, config)]
              .map(value => el("td", {}, value instanceof Node ? value : cell(value)))))))) : null,
      el("details", {}, el("summary", {}, "签署时快照摘要"), el("code", {}, signed.digest))) : null);
}

export async function evidencePage(config, user, route) {
  const runs = (await api.runs()).filter(item => item.status === "done");
  const run = route.id ? await api.run(route.id) : runs[0];
  if (!run?.result) return el("div", {class: "page"},
    pageHeading(config.modules[3], null), empty("成功执行一个批次后可以查看、签核和下载证据。"),
    el("a", {href: "#runs"}, config.modules[2]));

  const [review, clearance] = await Promise.all([api.review(run.id), api.clearance(run.id)]);
  const live = clearance.live;
  const issue = errorText();
  const button = el("button", {type: "button", onclick: async () => {
    button.disabled = true;
    issue.textContent = "";
    try {
      await download(await api.export(run.id), `evidence-${run.id}.json`);
    } catch (error) {
      issue.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  }}, "导出证据");
  const signing = el("div", {});
  signing.append(review ? signedView(review, config) : user.role === "reviewer" ?
    (live.signable ? reviewForm(run.id, data => signing.replaceChildren(signedView(data, config))) :
      empty(live.judgment === "无检测台账" ?
        "本批次无检测台账，无法按仪表号与检测时间核对，不能签署。" :
        "全部通过站点停送待复测，暂无放行对象，不能签署。")) :
    empty("待复核员签署。"));
  const revoking = el("div", {});
  revoking.append(user.role === "operator" ? revocationForm(async letter => {
    revoking.replaceChildren(el("p", {class: "feedback"}, `已登记撤销单 ${letter.code}，核对结果已刷新。`));
    window.setTimeout(() => location.reload(), 900);
  }) : empty("操作员可在此登记校准撤销单。"));
  const options = el("select", {"aria-label": "选择已完成的批次", onchange: event => {
    location.hash = `evidence/${event.target.value}`;
  }}, runs.map(item => el("option", {value: item.id, selected: item.id === run.id}, `#${item.id} ${item.case_title}`)));
  return el("div", {class: "page evidence"},
    pageHeading(config.modules[3], run.case_title, button),
    issue, options,
    el("section", {class: "feature evidence-summary"}, el("div", {}, el("h2", {}, "批次判定"), el("p", {}, run.result.summary)),
      el("details", {}, el("summary", {}, "证据摘要"), el("code", {}, run.digest))),
    el("dl", {class: "metrics"}, Object.entries(run.result.metrics).map(([label, value]) =>
      el("div", {}, el("dt", {}, label), el("dd", {}, cell(value))))),
    section("送电核对", clearanceView(live, config)),
    section("核对签署", signing),
    user.role === "operator" ? section("登记校准撤销单", revoking) : null,
    section("业务结果明细", run.result.rows.length ? resultTable(run.result.rows) : empty("此批次无明细。")));
}
