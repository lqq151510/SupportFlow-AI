package com.lqq.supportflow.model.application;
import com.lqq.supportflow.model.domain.ModelUrlPolicy; import java.net.URI; import java.time.Duration; import org.springframework.http.HttpHeaders; import org.springframework.stereotype.Service; import org.springframework.web.reactive.function.client.WebClient;
@Service public class ProbeModelConnectionService {
 private final ModelUrlPolicy urls; private final WebClient client;
 public ProbeModelConnectionService(ModelUrlPolicy urls, WebClient.Builder builder){this.urls=urls;this.client=builder.build();}
 public ProbeResult probe(String baseUrl,String apiKey){ urls.validate(baseUrl); try { URI endpoint=probeEndpoint(baseUrl); Integer status=client.get().uri(endpoint).header(HttpHeaders.AUTHORIZATION,"Bearer "+apiKey).exchangeToMono(response->reactor.core.publisher.Mono.just(response.statusCode().value())).block(Duration.ofSeconds(10)); return new ProbeResult(status!=null&&status<400,status==null?"no response":"HTTP "+status); } catch(Exception e){return new ProbeResult(false,"connection failed");} }
 private URI probeEndpoint(String baseUrl) {
  String root=baseUrl.endsWith("/")?baseUrl.substring(0,baseUrl.length()-1):baseUrl;
  URI parsed=URI.create(root);
  String path=parsed.getPath()==null?"":parsed.getPath();
  if (path.isBlank() || "/".equals(path)) root += "/v1";
  if (!root.endsWith("/v1")) root += "/v1";
  return URI.create(root + "/models");
 }
 public record ProbeResult(boolean reachable,String message) { }
}
