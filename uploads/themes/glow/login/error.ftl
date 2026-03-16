<#import "template.ftl" as layout>

<@layout.registrationLayout displayMessage=false; section>
  <#if section = "form">
    <div class="glow-page-wrapper">
      <#-- Sparkles background -->
      <div class="sparkles-background" id="sparkles-container"></div>

      <#-- Back button -->
      <#assign appBase = client.baseUrl!"" />
      <#if appBase?has_content>
        <div class="back-button-container">
          <a href="${appBase}" class="back-button">
            <div class="back-button-shine-1"></div>
            <div class="back-button-shine-2"></div>
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="back-icon">
              <path d="m12 19-7-7 7-7"></path>
              <path d="M19 12H5"></path>
            </svg>
            <span class="back-text">Back</span>
          </a>
        </div>
      </#if>

      <#-- Centered card -->
      <div class="glow-card">
        <div class="glow-card-shine-1"></div>
        <div class="glow-card-shine-2"></div>

        <div class="glow-card-content">
          <#-- Logo section -->
          <div class="logo-section">
            <#if appBase?has_content>
              <a href="${appBase}/" class="logo-link">
                <svg width="64" height="64" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" class="logo-icon">
                  <defs>
                    <linearGradient id="glow-gradient-error" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stop-color="#93C5FD"></stop>
                      <stop offset="50%" stop-color="#60A5FA"></stop>
                      <stop offset="100%" stop-color="#3B82F6"></stop>
                    </linearGradient>
                  </defs>
                  <rect width="32" height="32" rx="8" fill="url(#glow-gradient-error)"></rect>
                  <g transform="translate(16, 16) scale(0.667)">
                    <path d="M0 -11L2.59 -2.59L11 0L2.59 2.59L0 11L-2.59 2.59L-11 0L-2.59 -2.59L0 -11Z" fill="white"></path>
                  </g>
                </svg>
                <h1 class="glow-title">GLOW</h1>
              </a>
            <#else>
              <div class="logo-link">
                <svg width="64" height="64" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" class="logo-icon">
                  <defs>
                    <linearGradient id="glow-gradient-error" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stop-color="#93C5FD"></stop>
                      <stop offset="50%" stop-color="#60A5FA"></stop>
                      <stop offset="100%" stop-color="#3B82F6"></stop>
                    </linearGradient>
                  </defs>
                  <rect width="32" height="32" rx="8" fill="url(#glow-gradient-error)"></rect>
                  <g transform="translate(16, 16) scale(0.667)">
                    <path d="M0 -11L2.59 -2.59L11 0L2.59 2.59L0 11L-2.59 2.59L-11 0L-2.59 -2.59L0 -11Z" fill="white"></path>
                  </g>
                </svg>
                <h1 class="glow-title">GLOW</h1>
              </div>
            </#if>
          </div>

          <#-- Error content -->
          <div class="form-content">
            <div class="error-message-section">
              <#-- Error icon -->
              <div class="error-icon-wrapper">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="12" y1="8" x2="12" y2="12"></line>
                  <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
              </div>
              <#-- Error text -->
              <p class="error-text">
                <#if message?has_content>
                  ${kcSanitize(message.summary)?no_esc}
                <#else>
                  An unexpected error occurred. Please try again.
                </#if>
              </p>
            </div>

            <#-- Action buttons -->
            <div class="action-buttons-section">
              <#if client?? && client.baseUrl?has_content>
                <a class="action-button" href="${client.baseUrl}">
                  <div class="action-button-shine-1"></div>
                  <div class="action-button-shine-2"></div>
                  <div class="action-button-content">
                    <svg class="action-button-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
                      <polyline points="9 22 9 12 15 12 15 22"></polyline>
                    </svg>
                    <span class="action-button-text">Back to Home</span>
                  </div>
                </a>
              </#if>
              <a class="action-button" href="${url.loginUrl}">
                <div class="action-button-shine-1"></div>
                <div class="action-button-shine-2"></div>
                <div class="action-button-content">
                  <svg class="action-button-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"></path>
                    <polyline points="10 17 15 12 10 7"></polyline>
                    <line x1="15" y1="12" x2="3" y2="12"></line>
                  </svg>
                  <span class="action-button-text">Try Again</span>
                </div>
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>

    <script src="${url.resourcesPath}/js/sparkles.js"></script>
  </#if>
</@layout.registrationLayout>
