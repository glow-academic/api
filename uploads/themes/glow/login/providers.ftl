<#-- GENERATED FILE: do not edit manually -->
<#-- Generated at: 2026-05-22T10:39:24.839920 -->
<#--
  Provider mapping: department_id -> allowed IdP aliases

  Enumerated departments:
    - a2b369c1-a81e-5e02-98d5-dd42af15ae4a: University

  Enumerated IdP aliases:
    - default-idp-profile-102ea140-ca00-5c6a-9133-68e18a675a0e
    - default-idp-profile-da83dbb1-1693-5e47-a078-e03ab7d1cbf1

  Default-IdP aliases:
    - default-idp-profile-102ea140-ca00-5c6a-9133-68e18a675a0e
    - default-idp-profile-da83dbb1-1693-5e47-a078-e03ab7d1cbf1
-->

<#-- Departments to show in the picker -->
<#assign departments = [
  {"id": "a2b369c1-a81e-5e02-98d5-dd42af15ae4a", "title": "University"}
] />

<#-- Map department_id -> allowed IdP aliases -->
<#assign allowedProvidersByDept = {
  "a2b369c1-a81e-5e02-98d5-dd42af15ae4a": ["default-idp-profile-102ea140-ca00-5c6a-9133-68e18a675a0e", "default-idp-profile-da83dbb1-1693-5e47-a078-e03ab7d1cbf1"]
} />

<#-- Platform providers (only used when no departments exist) -->
<#assign platformProviders = [] />

<#function getAllowedProvidersForDepartment deptId>
  <#-- If departments exist, always use department-specific providers -->
  <#if departments?size gt 0>
    <#-- Default to first department if no department selected -->
    <#assign effectiveDeptId = deptId!"" />
    <#if !effectiveDeptId?has_content>
      <#assign effectiveDeptId = departments[0].id />
    </#if>
    <#if effectiveDeptId?has_content && allowedProvidersByDept[effectiveDeptId]??>
      <#assign deptProviders = allowedProvidersByDept[effectiveDeptId] />
      <#if deptProviders?size gt 0>
        <#return deptProviders>
      </#if>
    </#if>
    <#-- Fallback: return empty list if department has no providers -->
    <#return []>
  <#else>
    <#-- No departments exist: use platform providers -->
    <#return platformProviders>
  </#if>
</#function>

<#-- ═══ Login Entries (logins_resource with inline SVG icons) ═══ -->
<#assign loginEntries = [
  {"alias": "default-idp-profile-0507cd73-1b6f-549a-be41-4b7e093f5ce5", "display_name": "Continue as Benchmark", "icon_svg": "<svg width=\"24\" height=\"24\" xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\" > <path d=\"M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2\" /> <circle cx=\"12\" cy=\"7\" r=\"4\" /> </svg>", "login_type": "profile"},
  {"alias": "default-idp-profile-3431a662-0eae-511d-b665-776ecca6a8e9", "display_name": "Continue as Default Superadmin", "icon_svg": "<svg width=\"24\" height=\"24\" xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\" > <path d=\"M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2\" /> <circle cx=\"12\" cy=\"7\" r=\"4\" /> </svg>", "login_type": "profile"}
] />