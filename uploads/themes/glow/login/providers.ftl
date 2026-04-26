<#-- GENERATED FILE: do not edit manually -->
<#-- Generated at: 2026-04-26T16:00:24.054637 -->
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
  "a2b369c1-a81e-5e02-98d5-dd42af15ae4a": ["auth_learnloop_b88a56ef-0a5f-57d1-bd25-f5d829028757", "auth_google_0031836e-e1cc-5619-b2f8-c88864f44a80", "auth_microsoft_2ed1ab9f-eb32-5f4a-95f2-4904a4701687", "default-idp-profile-102ea140-ca00-5c6a-9133-68e18a675a0e", "default-idp-profile-da83dbb1-1693-5e47-a078-e03ab7d1cbf1"]
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
  {"alias": "auth_learnloop_b88a56ef-0a5f-57d1-bd25-f5d829028757", "display_name": "Continue with LearnLoop", "icon_svg": "<svg width=\"24\" height=\"24\" xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\" > <path d=\"M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z\" /> <path d=\"M20 3v4\" /> <path d=\"M22 5h-4\" /> <path d=\"M4 17v2\" /> <path d=\"M5 18H3\" /> </svg>", "login_type": "auth"},
  {"alias": "auth_google_0031836e-e1cc-5619-b2f8-c88864f44a80", "display_name": "Continue with Google", "icon_svg": "<svg width=\"24\" height=\"24\" xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\" > <circle cx=\"12\" cy=\"12\" r=\"10\" /> <path d=\"M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20\" /> <path d=\"M2 12h20\" /> </svg>", "login_type": "auth"},
  {"alias": "default-idp-profile-3431a662-0eae-511d-b665-776ecca6a8e9", "display_name": "Continue as Default Superadmin", "icon_svg": "<svg width=\"24\" height=\"24\" xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\" > <path d=\"M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2\" /> <circle cx=\"12\" cy=\"7\" r=\"4\" /> </svg>", "login_type": "profile"},
  {"alias": "default-idp-profile-0507cd73-1b6f-549a-be41-4b7e093f5ce5", "display_name": "Continue as Benchmark", "icon_svg": "<svg width=\"24\" height=\"24\" xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\" > <path d=\"M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2\" /> <circle cx=\"12\" cy=\"7\" r=\"4\" /> </svg>", "login_type": "profile"},
  {"alias": "auth_microsoft_2ed1ab9f-eb32-5f4a-95f2-4904a4701687", "display_name": "Continue with Microsoft", "icon_svg": "<svg width=\"24\" height=\"24\" xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\" > <rect width=\"18\" height=\"18\" x=\"3\" y=\"3\" rx=\"2\" /> <path d=\"M3 9h18\" /> <path d=\"M3 15h18\" /> <path d=\"M9 3v18\" /> <path d=\"M15 3v18\" /> </svg>", "login_type": "auth"}
] />