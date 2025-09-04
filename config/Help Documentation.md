# 数据网关配置文档 (Drilldown & API Mapping)

## 1. 核心理念
本数据网关由两个核心配置文件驱动，以实现动态、可配置的数据下钻功能。  

- **RESOURCE_API_MAP.json (API速查表)**:  
  负责定义系统中每个后端服务（Service）的技术契约。它像一本“通讯录”，告诉我们如何调用一个服务以及这个服务返回的是什么类型的数据。  

- **DRILLDOWN_ENRICHMENT_MAP.json (业务导航图)**:  
  负责定义数据之间的业务逻辑关系。它像一张“导航地图”，告诉我们当看到 A 类型的数据时，可以如何跳转到 B 类型的数据，并指导系统如何生成跳转所需的“探针”(Probe)。  

这两个文件协同工作，将前端交互、后端服务和业务逻辑完全解耦。  

---

## 2. RESOURCE_API_MAP.json (API速查表)

### 2.1 文件用途
此文件是所有后端服务的“注册中心”。每当系统中需要新增一个可被调用的服务时，都必须在此文件中进行注册。  
它的核心职责是将一个服务名称 (`service_name`) 映射到其关键的技术元数据。  

### 2.2 文件结构
文件是一个 JSON 对象，其 key 为服务名称（`service_name`），value 为该服务的元数据对象。  

```json
{
  "ServiceNameA": {
    "primary_id_param_name": "...",
    "returns_resource_type": "..."
  },
  "ServiceNameB": {
    "primary_id_param_name": "...",
    "returns_resource_type": "..."
  }
}
```
### 2.3 字段定义

| 字段名                | 类型   | 是否必须 | 描述                                                                                         | 示例                               |
|-----------------------|--------|----------|----------------------------------------------------------------------------------------------|------------------------------------|
| primary_id_param_name | string | 是       | 调用此服务时，其主要的、用于查询单条记录的 ID 参数的参数名称。例如，查询发票详情时，参数名叫 `invoiceId`。 | `"invoiceId"`                      |
| returns_resource_type | string | 是       | 此服务成功调用后，返回的数据在业务逻辑上属于哪种资源类型。这个值将作为 key 去 `DRILLDOWN_ENRICHMENT_MAP.json` 中查找对应的导航规则。 | `"invoice"`, `"project"`, `"project_summary_table"` |

---

### 2.4 完整示例

```json
{
  "RecordProjectService": {
    "primary_id_param_name": "projectId",
    "returns_resource_type": "project"
  },
  "FinishPayPaymentService": {
    "primary_id_param_name": "projectId",
    "returns_resource_type": "project_summary_table"
  },
  "PendingSalesInvoiceQuoteService": {
    "primary_id_param_name": "invoiceId",
    "returns_resource_type": "invoice"
  },
  "FinishRevenueService": {
    "primary_id_param_name": "projectId",
    "returns_resource_type": "project_summary_table"
  },
  "QueryBookService": {
    "primary_id_param_name": "projectId",
    "returns_resource_type": "project_summary_table"
  }
}
```
## 3. DRILLDOWN_ENRICHMENT_MAP.json (业务导航图)

### 3.1 文件用途
此文件定义了所有数据下钻的业务规则。  
它指导后端加工程序，在从 API 获取到原始数据后，如何检查数据内容，并为其注入可供前端使用的、指向下一步操作的“探针”(Probe)。  

---

### 3.2 文件结构
文件是一个 JSON 对象，其 key 为资源类型（`resource_type`，与 `RESOURCE_API_MAP.json` 中的 `returns_resource_type` 值对应），value 为该资源类型的导航规则对象。  

```json
{
  "ResourceTypeA": {
    "fields": {
      "__self__": { ... },
      "some_field_name": { ... }
    }
  },
  "ResourceTypeB": {
    "fields": { ... }
  }
}
```
### 3.3 字段定义

#### 3.3.1 fields 对象
`fields` 对象包含了针对该资源类型的所有下钻规则。  
它的 key 是触发规则的 **检查点**。  

---

#### 3.3.2 规则的“检查点” (fields 对象的 key)

- **"__self__" (特殊关键字)**  
  - **作用**: 定义当数据对象本身被视为一个整体时，其主要的、默认的下钻动作。  
  - **场景**: 在一个项目列表中，点击某一个项目，应该下钻到哪里？这个规则就定义了这个行为。  

- **具体的字段名 (例如 `"projectId"`)**  
  - **作用**: 定义基于数据对象内部某个特定字段的下钻动作。  
  - **场景**: 在查看一张发票的详情时，我们看到里面有一个 `projectId` 字段，我们希望这个字段可以点击并返回到对应的项目详情。这个规则就定义了这个行为。  

---

#### 3.3.3 规则内容 (fields 对象的 value)

| 字段名           | 类型   | 是否必须 | 描述                                                                                                        | 示例                                |
|------------------|--------|----------|-------------------------------------------------------------------------------------------------------------|-------------------------------------|
| target_service   | string | 是       | 当此规则被触发时，生成的探针应该指向的下一个服务名称。这个值必须是 `RESOURCE_API_MAP.json` 中已注册的服务名。 | `"FinishPayPaymentService"`         |
| source_id_field  | string | 是       | 用于生成探针 `params` 的 ID 值，应该从源数据对象的哪个字段里获取。<br>如果检查点是具体字段名，这里可使用 `"__self__"`，表示直接使用该字段的值。 | `"projectId"`, `"invoiceId"`, `"__self__"` |

---

### 3.4 完整示例

```json
{
  "project": {
    "fields": {
      "__self__": {
        "target_service": "FinishPayPaymentService",
        "source_id_field": "projectId"
      }
    }
  },
  "invoice": {
    "fields": {
      "__self__": {
        "target_service": "PendingSalesInvoiceQuoteService",
        "source_id_field": "invoiceId"
      },
      "projectId": {
        "target_service": "RecordProjectService",
        "source_id_field": "__self__"
      }
    }
  },
  "project_summary_table": {
    "fields": {
      "projectId": {
        "target_service": "RecordProjectService",
        "source_id_field": "__self__"
      }
    }
  }
}
```

---

## 4. 协同工作流程 (示例)

1. **获取数据**  
   前端执行了一个探针，调用了 `FinishPayPaymentService`。  
   后端调用该服务，获取到一份原始数据（例如，一个发票列表）。  

2. **识别类型**  
   后端程序查阅 `RESOURCE_API_MAP.json`，找到 `FinishPayPaymentService` 的条目，得知其 `returns_resource_type` 是 `project_summary_table`。  

3. **查找规则**  
   程序接着查阅 `DRILLDOWN_ENRICHMENT_MAP.json`，找到 `project_summary_table` 的规则。  

4. **应用规则**  
   程序发现有一条针对 `projectId` 字段的规则，于是检查返回数据中的 `projectId` 字段。  

5. **生成探针**  
   - 规则告诉它，目标服务是 `RecordProjectService`。  
   - 规则告诉它，ID 值就是 `projectId` 字段自身的值（`"source_id_field": "__self__"`）。  
   - 程序需要知道调用 `RecordProjectService` 时参数名叫什么，于是再次查阅 `RESOURCE_API_MAP.json`，找到其 `primary_id_param_name` 是 `projectId`。  

最终，程序生成新的探针，并注入到返回给前端的数据中：  

```json
{
  "service_name": "RecordProjectService",
  "params": {
    "projectId": "..."
  }
}
```
