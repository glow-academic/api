<#-- GENERATED FILE: do not edit manually -->
<#-- Generated at: 2026-03-03T07:04:04.524861 -->
<#--
  Provider mapping: department_id -> allowed IdP aliases

  Enumerated departments:
    - 019b3be4-3247-7cb0-bd74-9b2467b5e32d: University
    - 019c3f8c-b97b-7350-8d77-632e29b1c3f9: Organization

  Enumerated IdP aliases:
    - auth_google_019b3be4-3117-7aa4-aa34-0041aa51d1d8
    - auth_microsoft_019b3be4-3117-7afc-8d1d-a2815d70f294

  Default-IdP aliases:
-->

<#-- Departments to show in the picker -->
<#assign departments = [
  {"id": "019b3be4-3247-7cb0-bd74-9b2467b5e32d", "title": "University"},
  {"id": "019c3f8c-b97b-7350-8d77-632e29b1c3f9", "title": "Organization"}
] />

<#-- Map department_id -> allowed IdP aliases -->
<#assign allowedProvidersByDept = {
  "019b3be4-3247-7cb0-bd74-9b2467b5e32d": ["auth_microsoft_019b3be4-3117-7afc-8d1d-a2815d70f294"],
  "019c3f8c-b97b-7350-8d77-632e29b1c3f9": ["auth_google_019b3be4-3117-7aa4-aa34-0041aa51d1d8"]
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