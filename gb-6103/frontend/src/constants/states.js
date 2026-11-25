export const States = Object.freeze({
  queued: "等待执行", done: "已完成", failed: "执行失败",
});

export const Actions = Object.freeze({
  create_case: "登记资料", enqueue: "提交执行", done: "执行完成", failed: "执行失败", review: "复核签署",
  revocation: "登记撤销单",
});

export const ClearanceStates = Object.freeze({
  放行: "可送电", 恢复送电: "恢复送电", 停送: "停送待复测", 搁置: "搁置",
  无可送电站点: "无可送电站点", 无检测台账: "无检测台账",
  复测合格: "复测合格", 不合格: "不合格", 读数失效: "读数失效",
});
