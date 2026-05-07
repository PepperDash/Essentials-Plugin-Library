# Unit Testing Framework for Essentials Plugins

## Overview

This document outlines the plan to introduce a unit testing framework across PepperDash Essentials plugin repositories. The selected stack is **xUnit** for test execution and **Moq** for mocking dependencies.

> **Prerequisite:** Unit testing requires each plugin repository to first migrate to **.NET 8** (see [issue #21](https://github.com/PepperDash/Essentials-Plugin-Library/issues/21)). The Crestron SDK and the `net472`/`netstandard2.0` multi-targeting used today prevents standard test runners from executing tests outside the Crestron device runtime. Migrating to `net8.0` (or multi-targeting with a `net8.0` TFM) is therefore the critical prerequisite before any tests can run in CI.

---

## Why xUnit + Moq?

| Concern | Choice | Rationale |
|---|---|---|
| Test runner / framework | [xUnit](https://xunit.net/) | Modern, actively maintained, parallel test execution, first-class .NET support, used by most Microsoft open-source projects |
| Mocking library | [Moq](https://github.com/devlooped/moq) | Widely adopted, type-safe, fluent API, excellent documentation |
| Assertion | xUnit built-in + [FluentAssertions](https://fluentassertions.com/) (optional) | Readable failures; `FluentAssertions` can be added per-repo as desired |

---

## The Crestron SDK Challenge

### Problem

All Essentials plugins depend on `Crestron.SimplSharp.SDK` (or `Crestron.SimplSharpPro.SDK`). This SDK:

1. **Requires the Crestron device runtime.** Many types such as `CrestronEnvironment`, `CrestronConsole`, `CTimer`, `BasicTriList`, and hardware device classes throw `PlatformNotSupportedException` or `NullReferenceException` when instantiated outside a running Crestron processor.
2. **Provides no test doubles or seams.** The SDK ships compiled assemblies with no public interfaces for the majority of hardware-facing types.
3. **Has no NuGet package for `net8.0`.** The SDK targets `netstandard2.0` / `net472`, which means any test project that also targets `net8.0` must still reference the SDK, but the SDK is available on NuGet and loads fine on .NET 8 as long as you never call into Crestron runtime APIs.

### Consequence

Classes that **directly instantiate SDK types** (e.g., `new CrestronQueue<T>()`, `new CTimer(...)`) cannot be unit tested without mitigation strategies.

---

## Mitigation Strategies

### Strategy 1 — Introduce Abstraction Interfaces (Recommended)

Wrap Crestron SDK types behind thin interfaces that your plugin code depends on. In tests, provide `Moq` implementations of those interfaces.

**Example – abstracting `CrestronEnvironment`:**

```csharp
// Abstraction (lives in the plugin or a shared library)
public interface ICrestronEnvironment
{
    string DevicePlatform { get; }
    void Sleep(int milliseconds);
}

// Production implementation (wraps the real SDK)
public class CrestronEnvironmentAdapter : ICrestronEnvironment
{
    public string DevicePlatform => CrestronEnvironment.DevicePlatform.ToString();
    public void Sleep(int milliseconds) => CrestronEnvironment.Sleep(milliseconds);
}

// In plugin constructor — accept the interface
public class MyPlugin : EssentialsDevice
{
    private readonly ICrestronEnvironment _environment;

    public MyPlugin(string key, string name, ICrestronEnvironment environment)
        : base(key, name)
    {
        _environment = environment;
    }
}
```

**Test:**

```csharp
public class MyPluginTests
{
    [Fact]
    public void Constructor_SetsKey()
    {
        var envMock = new Mock<ICrestronEnvironment>();
        var plugin = new MyPlugin("key-1", "Test Device", envMock.Object);
        Assert.Equal("key-1", plugin.Key);
    }
}
```

### Strategy 2 — Extract Pure Logic into Testable Classes

Move business logic (protocol parsing, state machines, command building) into plain C# classes that have **no Crestron SDK dependency**. These classes are trivially testable.

**Example – protocol parser:**

```csharp
// No Crestron SDK dependency — fully testable
public static class SonyBraviaResponseParser
{
    public static PowerState ParsePowerResponse(string response)
    {
        if (response == "POW:ON\r") return PowerState.On;
        if (response == "POW:OFF\r") return PowerState.Off;
        return PowerState.Unknown;
    }
}
```

**Test:**

```csharp
public class SonyBraviaResponseParserTests
{
    [Theory]
    [InlineData("POW:ON\r", PowerState.On)]
    [InlineData("POW:OFF\r", PowerState.Off)]
    [InlineData("", PowerState.Unknown)]
    public void ParsePowerResponse_ReturnsExpectedState(string input, PowerState expected)
    {
        Assert.Equal(expected, SonyBraviaResponseParser.ParsePowerResponse(input));
    }
}
```

### Strategy 3 — Conditional Compilation / Stub Assemblies

For scenarios where abstracting is impractical, use a **stub assembly** that ships with the test project and re-implements the Crestron types as no-ops. This technique is sometimes called an "in-memory SDK shim."

```csharp
// In a test-only project: Crestron.SimplSharp.Stubs
namespace Crestron.SimplSharp
{
    public static class CrestronEnvironment
    {
        public static void Sleep(int ms) { /* no-op */ }
    }

    public class CTimer
    {
        public CTimer(TimerDelegate callback, long intervalMs) { }
        public void Stop() { }
    }
}
```

The test project references the stub assembly instead of the real SDK. This approach requires careful maintenance as the real SDK evolves.

### Strategy 4 — Integration Tests with Conditional Skip

For tests that genuinely need the Crestron runtime, mark them as integration tests and skip them in CI unless a device is available:

```csharp
[Fact(Skip = "Requires Crestron hardware")]
public void Hardware_PowerOn_SetsDisplayState()
{
    // only runs against a real device
}
```

---

## Implementation Plan

### Phase 1 — .NET 8 Migration (Issue #21, prerequisite)

1. Update each plugin `.csproj` to multi-target `net472;net8.0` (or migrate fully to `net8.0` where Crestron tooling allows).
2. Resolve any compilation errors introduced by the TFM change.
3. Ensure the build pipeline produces both target outputs.

### Phase 2 — Add Test Project per Plugin

1. In each plugin solution, add an `<PluginName>.Tests` project:

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <IsPackable>false</IsPackable>
    <Nullable>enable</Nullable>
  </PropertyGroup>

  <ItemGroup>
    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.12.0" />
    <PackageReference Include="xunit" Version="2.9.3" />
    <PackageReference Include="xunit.runner.visualstudio" Version="2.8.2" />
    <PackageReference Include="Moq" Version="4.20.72" />
    <PackageReference Include="coverlet.collector" Version="6.0.4" />
  </ItemGroup>

  <ItemGroup>
    <ProjectReference Include="..\<PluginName>\<PluginName>.csproj" />
  </ItemGroup>
</Project>
```

2. Add an `xunit.runner.json` to configure parallelism:

```json
{
  "$schema": "https://xunit.net/schema/current/xunit.runner.schema.json",
  "parallelizeTestCollections": true,
  "maxParallelThreads": 0
}
```

### Phase 3 — Introduce Abstraction Layers

1. Identify all direct usages of Crestron SDK types in plugin classes.
2. Extract interfaces (`ICrestronEnvironment`, `ICommunicationMonitor`, etc.) following Strategy 1 above.
3. Refactor plugin constructors to accept the interfaces (existing production callers pass the concrete adapters).

### Phase 4 — Write Initial Tests

Focus first on the highest-value, lowest-friction areas:

- **Response/command parsers** (Strategy 2 — no SDK dependency)
- **State machine logic** (Strategy 2)
- **Configuration deserialization** (plain `System.Text.Json` / `Newtonsoft.Json`)
- **Feedback/feedbacks helper logic**

### Phase 5 — CI Integration

Add a test step to each plugin's GitHub Actions workflow:

```yaml
- name: Run unit tests
  run: dotnet test --configuration Release --collect:"XPlat Code Coverage"

- name: Upload coverage
  uses: codecov/codecov-action@v4
  with:
    files: '**/coverage.cobertura.xml'
```

---

## Recommended Package Versions (as of 2026)

| Package | Version |
|---|---|
| `xunit` | 2.9.3 |
| `xunit.runner.visualstudio` | 2.8.2 |
| `Microsoft.NET.Test.Sdk` | 17.12.0 |
| `Moq` | 4.20.72 |
| `coverlet.collector` | 6.0.4 |
| `FluentAssertions` *(optional)* | 7.0.0 |

---

## Example Repository Structure

```
epi-sony-bravia/
├── src/
│   └── EpiSonyBravia/
│       ├── EpiSonyBravia.csproj          # net472;net8.0
│       ├── SonyBraviaDevice.cs
│       ├── SonyBraviaResponseParser.cs   # no SDK dependency
│       └── Abstractions/
│           └── ICrestronEnvironment.cs
└── tests/
    └── EpiSonyBravia.Tests/
        ├── EpiSonyBravia.Tests.csproj    # net8.0 only
        ├── SonyBraviaResponseParserTests.cs
        └── SonyBraviaDeviceTests.cs
```

---

## References

- [xUnit Documentation](https://xunit.net/docs/getting-started/netcore/cmdline)
- [Moq QuickStart](https://github.com/devlooped/moq/wiki/Quickstart)
- [FluentAssertions](https://fluentassertions.com/)
- [Coverlet (code coverage)](https://github.com/coverlet-coverage/coverlet)
- [Issue #21 — Migrate to .NET 8](https://github.com/PepperDash/Essentials-Plugin-Library/issues/21)
