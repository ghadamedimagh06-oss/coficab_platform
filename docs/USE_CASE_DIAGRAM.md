# CofICab Platform Global Use-Case Diagram

This is a global user-interaction view. Background automation such as watchdogs, schedulers, trackers, optimization jobs, KPI jobs, and notifications is grouped into one helper actor: **System**.

```mermaid
flowchart LR
    %% Real actors - left side
    viewer["Viewer"]
    planner["Planner / Dispatcher"]
    admin["Administrator"]
    driver["Driver"]

    planner -.->|inherits| viewer
    admin -.->|inherits| planner

    %% Platform - center
    subgraph platform["CofICab OptiRoute Platform"]
        direction LR

        UC_Auth(("Access Platform"))
        UC_Dashboard(("Monitor Operations"))
        UC_Data(("Manage Planning Data"))
        UC_Planning(("Manage Transport Planning"))
        UC_Execution(("Manage Mission Execution"))
        UC_Resources(("Manage Resources"))
        UC_Admin(("Administer Platform"))

        UC_Auth ~~~ UC_Dashboard
        UC_Dashboard ~~~ UC_Data
        UC_Data ~~~ UC_Planning
        UC_Planning ~~~ UC_Execution
        UC_Execution ~~~ UC_Resources
        UC_Resources ~~~ UC_Admin
    end

    %% Helper actor - right side
    system["System"]

    %% User interactions
    viewer --> UC_Auth
    viewer --> UC_Dashboard

    planner --> UC_Data
    planner --> UC_Planning
    planner --> UC_Execution
    planner --> UC_Resources

    admin --> UC_Admin

    driver --> UC_Execution

    %% System helper interactions
    system --> UC_Data
    system --> UC_Planning
    system --> UC_Dashboard
    system --> UC_Execution

    %% Use-case relationships
    UC_Data -.->|include| UC_Auth
    UC_Planning -.->|include| UC_Data
    UC_Execution -.->|include| UC_Planning
    UC_Resources -.->|include| UC_Auth
    UC_Admin -.->|include| UC_Auth

    UC_Execution -.->|extend| UC_Planning
    UC_Admin -.->|extend| UC_Resources
```

## Notes

- **Viewer** only observes platform information.
- **Planner / Dispatcher** manages daily operational work.
- **Administrator** inherits planner capabilities and adds administration.
- **Driver** interacts only with mission execution.
- **System** represents all automated/background helpers.
