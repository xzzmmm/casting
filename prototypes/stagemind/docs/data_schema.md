# StageMind 结构化数据规范

与项目方案书 4.2 节一致。三类核心数据分别对应后端 `app/models.py` 中的 `LogItem`、`BlockingTrack`、`Issue`。

## 1. 排练日志条目（log_items）

```json
{
  "id": 101,
  "rehearsal_id": 3,
  "ts_start": 130.5,
  "ts_end": 156.0,
  "item_type": "表演",
  "speakers": ["导演"],
  "summary": "第二幕开场，甲的情绪转折不够，重音放在‘我早就知道’上",
  "decision": "明天再走一遍开场，重点练重音",
  "status": "待解决",
  "actors": ["甲"],
  "tags": ["台词", "情绪"]
}
```

`item_type` 取值：舞台 / 道具 / 灯光 / 音效 / 表演 / 其他。
`status` 取值：已确定 / 待解决。

## 2. 台位轨迹点（blocking_tracks）

```json
{
  "id": 5001,
  "rehearsal_id": 3,
  "actor": "甲",
  "frame_ts": 130.5,
  "x": 0.42,
  "y": 0.61,
  "confidence": 0.87
}
```

`x`、`y` 为归一化舞台坐标（0 到 1，0,0 为舞台观众席左下角）。同一演员按 `frame_ts` 升序排列即为其动线。

## 3. 问题条目（issues）

```json
{
  "id": 7,
  "rehearsal_id": 3,
  "source_item_id": 101,
  "description": "第二幕开场重音问题",
  "owner": "导演",
  "status": "open",
  "created_at": "2026-10-12T21:30:00",
  "resolved_at": null
}
```

`status` 取值：open（待解决）/ resolved（已解决）；`resolved_at` 在状态变为 resolved 时写入。
