<#import "template.ftl" as layout>
<@layout.registrationLayout; section>
  <#if section = "form">
    <form id="kc-expired-form" action="${url.loginRestartFlowUrl}" method="post">
      <input type="hidden" name="restart" value="true" />
    </form>
    <script>
      document.getElementById("kc-expired-form").submit();
    </script>
  </#if>
</@layout.registrationLayout>
