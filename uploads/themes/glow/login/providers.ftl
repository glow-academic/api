<#-- GENERATED FILE: do not edit manually -->
<#-- Generated at: 2026-04-19T09:41:26.119598 -->
<#--
  Provider mapping: department_id -> allowed IdP aliases

  Enumerated departments:
    - a2b369c1-a81e-5e02-98d5-dd42af15ae4a: University

  Enumerated IdP aliases:
    - auth_google_0031836e-e1cc-5619-b2f8-c88864f44a80
    - auth_learnloop_b88a56ef-0a5f-57d1-bd25-f5d829028757
    - auth_microsoft_2ed1ab9f-eb32-5f4a-95f2-4904a4701687
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
  "a2b369c1-a81e-5e02-98d5-dd42af15ae4a": ["auth_learnloop_b88a56ef-0a5f-57d1-bd25-f5d829028757", "auth_google_0031836e-e1cc-5619-b2f8-c88864f44a80", "auth_microsoft_2ed1ab9f-eb32-5f4a-95f2-4904a4701687", "default-idp-profile-da83dbb1-1693-5e47-a078-e03ab7d1cbf1", "default-idp-profile-102ea140-ca00-5c6a-9133-68e18a675a0e"]
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