# 岚北轨检日表仓

岚北轨检资料中心整理晨班测量组的逐行读数，石桥区站在没有源仓连接时安装正式日表并核账。午班修订员可以更正读数和重排行位。夜班按自己所见的版号提交属地批注，即使原行已经换位，也能继续复核同一条观测。

## 运行

使用 Python 3.11 标准库和 SQLite。在项目根目录运行控制台提供的回归入口与工作日样例。

```sh
python3 -B check_project.py
python3 -B demo.py
```

也可直接发现全套标准库测试。

```sh
python3 -B -m unittest discover -s tests -t .
```

样例读取 `samples/shift.json`，在测试临时目录分别建立源仓和区站仓。两条原测各为 7 mm，初版按东线、西线顺序实收。换位后西线的「已核」在现行行位 1。夜班对初版行位 1 交「待现场复核」，东线在现行行位 2 收到批注。两版合计均为 14 mm。

## 一天的操作

1. 晨班测量组提交有序观测。归档员登记源批，逐行保留本站和原测记录号。
2. 归档员把该日的登记批冻结为正式初版。初版行位从 1 起按登记顺序分配。
3. 发行员按正式版号取得固定件，区站收到字节后离线安装并保存回执。
4. 午班修订员按当前正式父版提交一组换位、改值、复制、撤回或补入操作。仓库核定最终行位后一次冻结。
5. 发行员按新正式版号领件。旧发行号仍对应独立固定的原件。
6. 区站安装衔接现行版的后继件，现行行表、历史位置和回执同次提交。
7. 夜班以日表、所见版和旧行位写属地批注。区站解析原行并在同一次写入中检查它仍存续。
8. 核账员在同一接收视图内取得按现行行位排列的读值、出处、批注和精确合计。

## Python 接口

`warehouse_db.open_database(path)` 返回源仓 SQLite 连接。开始前依次调用 `intake.store.initialize_intake`、`revision.history.initialize_revision` 和 `dispatch.catalog.initialize_catalog`。`mirror.store.open_mirror(path)` 打开并初始化另一份数据库。调用者负责关闭连接。会开启事务的入口要求连接空闲，区站和源仓使用不同数据库。初始化可以重跑，保留既有数据和人工修改。

| 接口 | 输入与结果 |
| --- | --- |
| `intake.batches.register(db, batch_id, table_id, observations)` | 接受列表或元组。每项为 `Observation` 或包含 `reading_mm` 与 `origin` 的字典。出处包含字符串 `station` 和 `record`。返回 `RegisteredBatch`，可用 `get_registered_batch(db, batch_id)` 读取。 |
| `revision.book.revise(db, table_id, batch_id=...)` | 冻结归属当前日表的已登记源批，返回初版号。 |
| `revision.book.revise(db, table_id, parent=..., edits=...)` | 在当前正式父版上一次提交编辑，返回新正式修订号。`revision.history.get_revision` 可按日表和版号查旧版，`get_head` 返回现行正式版号。 |
| `dispatch.issue.issue(db, table_id, revision)` | 返回 `IssuedPackage`，含发行号、日表、父子版、固定 `payload` 字节及摘要。`read_issued_package(db, issue_id)` 按发行号复领。 |
| `mirror.install.install(station, payload)` | 校验并安装一份固定件，返回 `Receipt`。已安装同件返回原回执。`mirror.receipts.get_receipt` 可按回执号单独查询。 |
| `audit.annotations.annotate(station, table_id, seen_revision, slot, text)` | 返回 `AnnotationUpdate`，包含本次记录号及提交时的目标现行行位。文本原样保存，包括空文本及前后空白。 |
| `audit.reconcile.read(station, table_id)` | 返回 `Ledger`，包含实收版、按行位排序的明细和整数 `total_mm`。未实收返回 `None`，已实收空表返回空行组和零。 |

业务拒绝以 `ValueError` 表示。未知源批、正式修订和回执的查阅方法返回 `None`，未知发行号拒绝领件。SQLite 操作及提交失败保留原异常，调用方可在排除故障后重试。批号全源仓唯一，日表独立编号。日表号、批号和出处字段为非空白 Unicode 文本。行位及版号为正的 SQLite 整数。

## 编辑与计量

| 操作 | 字段 | 效果 |
| --- | --- | --- |
| `move` | `slot`, `to` | 把父版原行移至目标行位。 |
| `copy` | `slot`, `to` | 用父版原行的读值及出处建立新行。 |
| `correct` | `slot`, `reading_mm` | 更正父版原行的读值，保留出处和归属。 |
| `withdraw` | `slot` | 终止父版原行。 |
| `insert` | `to`, `reading_mm`, `origin` | 在目标位置建立新行。 |

每项均含 `op`。来源 `slot` 始终指向同一个固定父版。移动可与更正作用于同一原行，复制仍读取父版值。撤回可与复制或同址补入同组发生。最终占位冲突和同一原行上互不相容的编辑使整组拒绝。空编辑组可冻结一个内容延续的后继版。历史正式版保持固定。

整数毫米允许零和负值。读值接收 Python `int`，并以无损文本写入 SQLite 及固定件，核账对返回的行使用整数加总。等值观测逐条保留，未批注以 `None` 表示。固定件使用规范 JSON 字节及 SHA-256 完整性校验，适用于中心与区站约定的交付渠道。区站按包内父子版关系和本地实收状态判断安装资格。缺父版、材料无效或提交失败时，已有账和回执仍可复查。

属地批注由区站保管。换位前后可用已实收的历史地址定位原行，前提是该行仍处于现行版。撤回后，即使同一位置或同一出处再次出现，旧地址也失去写入资格。系统支持同一日表的线性修订。分叉合并、跨日表移位及批注回传均在本系统范围之外。
