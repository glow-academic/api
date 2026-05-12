<#import "template.ftl" as layout>
<#include "providers.ftl">

<#--
  Theme bridge: read the same signal next-themes uses in the Next.js
  app and toggle `.dark` / `.light` on <html> BEFORE the page paints,
  so the login surface inherits whatever theme the user chose in the
  app. Resolution order:
    1. ``?glow_theme=`` URL parameter (works locally + prod; survives
       even when cookies can't cross origins).
    2. ``glow_theme`` cookie (parent-domain in prod, host-only in dev).
    3. (fallback) OS preference via @media (prefers-color-scheme).
  Inline + executed before <body> renders, so there's no flash.
-->
<script>
(function() {
  try {
    var u = new URLSearchParams(window.location.search).get('glow_theme');
    var m = document.cookie.match(/(?:^|; )glow_theme=([^;]+)/);
    var t = u || (m && decodeURIComponent(m[1])) || '';
    var r = document.documentElement;
    if (t === 'dark') { r.classList.add('dark'); r.classList.remove('light'); }
    else if (t === 'light') { r.classList.add('light'); r.classList.remove('dark'); }
    // 'system' or unset → leave classes off so @media prefers-color-scheme wins
  } catch (e) { /* no-op: fall back to OS preference */ }
})();
</script>

<@layout.registrationLayout displayInfo=social.displayInfo; section>
  <#if section = "form">
    <#-- Read department from URL parameter -->
    <#assign departmentId = "" />
    <#if param?? && param.department??>
      <#assign departmentId = param.department?string />
    </#if>
    <#assign allowed = getAllowedProvidersForDepartment(departmentId) />
    
    <#-- Find selected department name -->
    <#assign selectedDeptName = "Default Account" />
    <#if departmentId?has_content>
      <#list departments as d>
        <#if d.id == departmentId>
          <#assign selectedDeptName = d.title />
          <#break />
        </#if>
      </#list>
    </#if>
    
    <#-- Full-page wrapper matching Next.js structure -->
    <div class="glow-page-wrapper">
      <#-- Sparkles background -->
      <div class="sparkles-background" id="sparkles-container"></div>
      
      <#assign appBase = client.baseUrl!"" />
      
      <#-- Centered card -->
      <div class="glow-card">
        <#-- Shine effects -->
        <div class="glow-card-shine-1"></div>
        <div class="glow-card-shine-2"></div>
        
        <#-- Content container -->
        <div class="glow-card-content">
          <#-- Logo section -->
          <div class="logo-section">
            <div class="logo-link">
              <#-- Page gradient now uses --background / --accent (light
                   surfaces in light mode, dark in dark mode), so the
                   icon rect uses --primary (the brand color, which
                   contrasts the page bg in both modes) and the inner
                   sparkle uses --primary-foreground (contrasts the
                   brand rect). Same contrast-pair rule applied in the
                   other direction now that the page itself is themed. -->
              <svg width="64" height="64" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" class="logo-icon">
                <defs>
                  <linearGradient id="glow-gradient-login" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="var(--primary, #93C5FD)"></stop>
                    <stop offset="50%" stop-color="var(--primary, #60A5FA)"></stop>
                    <stop offset="100%" stop-color="var(--accent, #3B82F6)"></stop>
                  </linearGradient>
                </defs>
                <rect width="32" height="32" rx="8" fill="url(#glow-gradient-login)"></rect>
                <g transform="translate(16, 16) scale(0.667)">
                  <path d="M0 -11L2.59 -2.59L11 0L2.59 2.59L0 11L-2.59 2.59L-11 0L-2.59 -2.59L0 -11Z" fill="var(--primary-foreground, white)"></path>
                </g>
              </svg>
              <h1 class="glow-title">GLOW</h1>
            </div>
          </div>
          
          <#-- Form content -->
          <div class="form-content">
            <#-- Department Picker (only show if departments exist, no "Default" option) -->
            <#if departments?size gt 0>
              <div class="department-picker-wrapper">
                <select id="department" name="department" class="department-select">
                  <#list departments as d>
                    <option value="${d.id}" <#if departmentId == d.id>selected</#if>>${d.title}</option>
                  </#list>
                </select>
              </div>
              
              <script>
                // Expose data for department-select.js
                window.departmentsData = [
                  <#list departments as d>
                  {id: "${d.id}", title: "${d.title}"}<#sep>,
                  </#list>
                ];
                window.allowedProvidersByDept = {
                  <#list allowedProvidersByDept?keys as deptId>
                  "${deptId}": [<#list allowedProvidersByDept[deptId] as alias>"${alias}"<#sep>, </#list>]<#sep>,
                  </#list>
                };
                window.platformProviders = [<#list platformProviders as p>"${p}"<#sep>, </#list>];
              </script>
              <script src="${url.resourcesPath}/js/department-select.js"></script>
            </#if>
            
            <#-- Username/password form (hidden by default, shown if needed) -->
            <#if realm.password>
              <form id="kc-form-login" onsubmit="login.disabled = true; return true;" action="${url.loginAction}" method="post" style="display: none;">
                <div class="${properties.kcFormGroupClass!}">
                  <label for="username" class="${properties.kcLabelClass!}">
                    <#if !realm.loginWithEmailAllowed>
                      ${msg("username")}
                    <#elseif !realm.registrationEmailAsUsername>
                      ${msg("usernameOrEmail")}
                    <#else>
                      ${msg("email")}
                    </#if>
                  </label>
                  <#if usernameEditDisabled??>
                    <input tabindex="1" id="username" class="${properties.kcInputClass!}" name="username" value="${(login.username!'')}" type="text" disabled />
                  <#else>
                    <input tabindex="1" id="username" class="${properties.kcInputClass!}" name="username" value="${(login.username!'')}" type="text" autofocus autocomplete="off" aria-invalid="<#if messagesPerField.existsError('username','password')>true</#if>" />
                  </#if>
                </div>
                <div class="${properties.kcFormGroupClass!}">
                  <div class="${properties.kcLabelWrapperClass!}">
                    <label for="password" class="${properties.kcLabelClass!}">${msg("password")}</label>
                    <#if realm.resetPasswordAllowed>
                      <span class="${properties.kcFormOptionsWrapperClass!}">
                        <a tabindex="5" class="${properties.kcFormForgotPasswordClass!}" href="${url.loginResetCredentialsUrl}">${msg("doForgotPassword")}</a>
                      </span>
                    </#if>
                  </div>
                  <input tabindex="2" id="password" class="${properties.kcInputClass!}" name="password" type="password" autocomplete="off" aria-invalid="<#if messagesPerField.existsError('username','password')>true</#if>" />
                </div>
                <div class="${properties.kcFormGroupClass!} ${properties.kcFormSettingClass!}">
                  <div id="kc-form-options">
                    <#if realm.rememberMe && !usernameEditDisabled??>
                      <div class="checkbox">
                        <label>
                          <#if login.rememberMe??>
                            <input tabindex="3" id="rememberMe" name="rememberMe" type="checkbox" checked> ${msg("rememberMe")}
                          <#else>
                            <input tabindex="3" id="rememberMe" name="rememberMe" type="checkbox"> ${msg("rememberMe")}
                          </#if>
                        </label>
                      </div>
                    </#if>
                  </div>
                </div>
                <div id="kc-form-buttons" class="${properties.kcFormGroupClass!}">
                  <input type="hidden" id="id-hidden-input" name="credentialId" <#if auth.selectedCredential?has_content>value="${auth.selectedCredential}"</#if>/>
                  <input tabindex="4" class="${properties.kcButtonClass!} ${properties.kcButtonPrimaryClass!} ${properties.kcButtonBlockClass!} ${properties.kcButtonLargeClass!}" name="login" id="kc-login" type="submit" value="${msg("doLogIn")}"/>
                </div>
              </form>
            </#if>
            
            <#-- Provider buttons and action buttons (all styled consistently) -->
            <div class="action-buttons-section">
              <#-- Provider buttons (all rendered, filtered client-side by JavaScript) -->
              <#-- Includes regular IdPs (Google, Microsoft, etc.) and default-idp instances -->
              <#if social.providers?? && social.providers?size gt 0>
                <#-- Separate providers into auth providers, profile providers, and guest providers -->
                <#assign authProviders = [] />
                <#assign profileProviders = [] />
                <#assign guestProviders = [] />
                <#list social.providers as p>
                  <#if p.alias?starts_with("default-idp-guest-")>
                    <#assign guestProviders = guestProviders + [p] />
                  <#elseif p.alias?starts_with("default-idp-profile-")>
                    <#assign profileProviders = profileProviders + [p] />
                  <#else>
                    <#assign authProviders = authProviders + [p] />
                  </#if>
                </#list>
                <#-- Combine: auth providers first, then profile providers -->
                <#assign nonGuestProviders = authProviders + profileProviders />
                
                <#-- Render non-guest providers first (all rendered, filtered client-side) -->
                <#list nonGuestProviders as p>
                  <#assign loadingText = "Signing in..." />
                  <#-- Find matching loginEntries entry for this provider -->
                  <#assign matchedLogin = "" />
                  <#if loginEntries??>
                    <#list loginEntries as entry>
                      <#if entry.alias == p.alias>
                        <#assign matchedLogin = entry />
                        <#break />
                      </#if>
                    </#list>
                  </#if>
                  <a id="social-${p.alias}"
                     class="action-button"
                     href="${p.loginUrl}"
                     <#if !allowed?seq_contains(p.alias)>style="display: none;"</#if>
                     data-loading-text="${loadingText}">
                    <div class="action-button-shine-1"></div>
                    <div class="action-button-shine-2"></div>
                    <div class="action-button-content">
                      <#-- Icon: prefer inline SVG from loginEntries, fall back to CSS icon classes -->
                      <#if matchedLogin?has_content && matchedLogin.icon_svg?has_content>
                        <span class="action-button-icon action-button-icon-inline">${matchedLogin.icon_svg?no_esc}</span>
                      <#else>
                        <#-- Fallback: CSS icon class logic -->
                        <#assign iconClassToUse = "" />
                        <#if p.iconClasses?has_content>
                          <#assign iconClassToUse = p.iconClasses />
                        <#elseif p.config?? && p.config.iconClasses??>
                          <#assign iconClassToUse = p.config.iconClasses />
                        <#elseif p.alias?starts_with("auth_")>
                          <#assign aliasParts = p.alias?split("_") />
                          <#if (aliasParts?size >= 2)>
                            <#assign iconClassToUse = "kc-social-icon-${aliasParts[1]}" />
                          </#if>
                        </#if>
                        <#if iconClassToUse?has_content>
                          <i class="${properties.kcCommonLogoIdP!} ${iconClassToUse} action-button-icon" aria-hidden="true"></i>
                        <#elseif p.alias?starts_with("default-idp-")>
                          <svg class="action-button-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path>
                          </svg>
                        </#if>
                      </#if>
                      <#-- Spinner (hidden by default, shown when loading) -->
                      <div class="action-button-spinner"></div>
                      <#-- Text: prefer display_name from loginEntries, fall back to existing logic -->
                      <#if matchedLogin?has_content && matchedLogin.display_name?has_content>
                        <span class="action-button-text">${matchedLogin.display_name}</span>
                      <#elseif p.alias?starts_with("default-idp-profile-")>
                        <span class="action-button-text">Continue as ${p.displayName!}</span>
                      <#elseif p.alias?starts_with("default-idp-")>
                        <span class="action-button-text">Continue as Default Account</span>
                      <#else>
                        <span class="action-button-text">Continue with ${p.displayName!}</span>
                      </#if>
                      <#-- Loading text (hidden by default) -->
                      <span class="action-button-loading-text"></span>
                    </div>
                  </a>
                </#list>
                
                <#-- Filter guest providers to only those allowed for current department (for OR divider check) -->
                <#-- Use explicit prefix match to avoid false positives -->
                <#assign visibleGuestProviders = [] />
                <#list guestProviders as p>
                  <#if p.alias?starts_with("default-idp-guest-") && allowed?seq_contains(p.alias)>
                    <#assign visibleGuestProviders = visibleGuestProviders + [p] />
                  </#if>
                </#list>
                
                <#-- Count visible non-guest providers (for OR divider check) -->
                <#assign visibleNonGuestCount = 0 />
                <#list nonGuestProviders as p>
                  <#if allowed?seq_contains(p.alias)>
                    <#assign visibleNonGuestCount = visibleNonGuestCount + 1 />
                  </#if>
                </#list>
                
                <#-- Add OR divider only if we have both visible non-guest and visible guest providers -->
                <#if visibleNonGuestCount gt 0 && visibleGuestProviders?size gt 0>
                  <div class="or-divider">
                    <div class="or-divider-text">
                      <span>Or</span>
                    </div>
                  </div>
                </#if>
                
                <#-- Render guest providers (all rendered, filtered client-side) -->
                <#list guestProviders as p>
                  <#assign loadingText = "Accessing..." />
                  <#-- Find matching loginEntries entry for this guest provider -->
                  <#assign matchedLogin = "" />
                  <#if loginEntries??>
                    <#list loginEntries as entry>
                      <#if entry.alias == p.alias>
                        <#assign matchedLogin = entry />
                        <#break />
                      </#if>
                    </#list>
                  </#if>
                  <a id="social-${p.alias}"
                     class="action-button"
                     href="${p.loginUrl}"
                     <#if !allowed?seq_contains(p.alias)>style="display: none;"</#if>
                     data-loading-text="${loadingText}">
                    <div class="action-button-shine-1"></div>
                    <div class="action-button-shine-2"></div>
                    <div class="action-button-content">
                      <#-- Icon: prefer inline SVG from loginEntries, fall back to existing -->
                      <#if matchedLogin?has_content && matchedLogin.icon_svg?has_content>
                        <span class="action-button-icon action-button-icon-inline">${matchedLogin.icon_svg?no_esc}</span>
                      <#elseif p.iconClasses?has_content>
                        <i class="${properties.kcCommonLogoIdP!} ${p.iconClasses!} action-button-icon" aria-hidden="true"></i>
                      <#else>
                        <svg class="action-button-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path>
                        </svg>
                      </#if>
                      <#-- Spinner (hidden by default, shown when loading) -->
                      <div class="action-button-spinner"></div>
                      <#-- Text: prefer display_name from loginEntries, fall back -->
                      <#if matchedLogin?has_content && matchedLogin.display_name?has_content>
                        <span class="action-button-text">${matchedLogin.display_name}</span>
                      <#else>
                        <span class="action-button-text">Continue as Guest</span>
                      </#if>
                      <#-- Loading text (hidden by default) -->
                      <span class="action-button-loading-text"></span>
                    </div>
                  </a>
                </#list>
              </#if>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <#-- Load sparkles JavaScript from external file to avoid CSP issues -->
    <script src="${url.resourcesPath}/js/sparkles.js"></script>
    <#-- Load login interactions JavaScript for loading states -->
    <script src="${url.resourcesPath}/js/login-interactions.js"></script>
  </#if>
</@layout.registrationLayout>
