<#import "template.ftl" as layout>

<@layout.registrationLayout displayMessage=false; section>
  <#if section = "form">
    <div class="glow-page-wrapper">
      <#-- Sparkles background -->
      <div class="sparkles-background" id="sparkles-container"></div>

      <#-- Centered card -->
      <div class="glow-card">
        <div class="glow-card-shine-1"></div>
        <div class="glow-card-shine-2"></div>

        <div class="glow-card-content">
          <#-- Logo section -->
          <div class="logo-section">
            <div class="logo-link">
              <svg width="64" height="64" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" class="logo-icon">
                <defs>
                  <linearGradient id="glow-gradient-logout" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#93C5FD"></stop>
                    <stop offset="50%" stop-color="#60A5FA"></stop>
                    <stop offset="100%" stop-color="#3B82F6"></stop>
                  </linearGradient>
                </defs>
                <rect width="32" height="32" rx="8" fill="url(#glow-gradient-logout)"></rect>
                <g transform="translate(16, 16) scale(0.667)">
                  <path d="M0 -11L2.59 -2.59L11 0L2.59 2.59L0 11L-2.59 2.59L-11 0L-2.59 -2.59L0 -11Z" fill="white"></path>
                </g>
              </svg>
              <h1 class="glow-title">GLOW</h1>
            </div>
          </div>

          <#-- Logout content -->
          <div class="form-content">
            <div class="logout-message-section">
              <div class="logout-icon-wrapper">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                  <polyline points="16 17 21 12 16 7"></polyline>
                  <line x1="21" y1="12" x2="9" y2="12"></line>
                </svg>
              </div>
              <p class="logout-text">Are you sure you want to sign out?</p>
            </div>

            <div class="action-buttons-section">
              <form action="${url.logoutConfirmAction}" method="POST">
                <input type="hidden" name="session_code" value="${logoutConfirm.code}">
                <button type="submit" class="action-button" id="kc-logout" name="confirmLogout">
                  <div class="action-button-shine-1"></div>
                  <div class="action-button-shine-2"></div>
                  <div class="action-button-content">
                    <svg class="action-button-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                      <polyline points="16 17 21 12 16 7"></polyline>
                      <line x1="21" y1="12" x2="9" y2="12"></line>
                    </svg>
                    <span class="action-button-text">Sign Out</span>
                  </div>
                </button>
              </form>

              <#if !logoutConfirm.skipLink && (client.baseUrl)?has_content>
                <a class="action-button action-button-secondary" href="${client.baseUrl}">
                  <div class="action-button-shine-1"></div>
                  <div class="action-button-shine-2"></div>
                  <div class="action-button-content">
                    <span class="action-button-text">Cancel</span>
                  </div>
                </a>
              </#if>
            </div>
          </div>
        </div>
      </div>
    </div>

    <script src="${url.resourcesPath}/js/sparkles.js"></script>
  </#if>
</@layout.registrationLayout>
