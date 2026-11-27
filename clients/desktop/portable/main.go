// Build with build.sh to embed the matching application and study snapshot.
package main

import (
    "embed"
    "encoding/json"
    "errors"
    "fmt"
    "io/fs"
    "log"
    "net"
    "net/http"
    "os"
    "os/exec"
    "path/filepath"
    "runtime"
    "time"
)

//go:embed assets/*
var bundle embed.FS

func browserPath() (string, error) {
    candidates := []string{"msedge", "google-chrome", "chromium", "chromium-browser"}
    for _, variable := range []string{"ProgramFiles(x86)", "ProgramFiles", "LocalAppData"} {
        if dir := os.Getenv(variable); dir != "" {
            candidates = append(candidates, filepath.Join(dir,"Microsoft","Edge","Application","msedge.exe"),
                filepath.Join(dir,"Google","Chrome","Application","chrome.exe"))
        }
    }
    for _, name := range candidates {
        if path, err := exec.LookPath(name); err == nil { return path, nil }
    }
    return "", errors.New("请安装 Microsoft Edge、Chrome 或 Chromium 后打开桌面应用")
}

func run() error {
    files, err := fs.Sub(bundle,"assets")
    if err != nil { return err }
    mux := http.NewServeMux()
    mux.Handle("/",http.FileServer(http.FS(files)))
    mux.HandleFunc("/api/config",func(w http.ResponseWriter,r *http.Request){
        w.Header().Set("Content-Type","application/json")
        fmt.Fprint(w,"{}")
    })
    check := len(os.Args)>1 && os.Args[1]=="--check"
    address := "127.0.0.1:38421"
    if check { address = "127.0.0.1:0" }
    listener,err := net.Listen("tcp",address)
    if err != nil { return err }
    server := &http.Server{Handler:mux, ReadHeaderTimeout:5*time.Second}
    defer server.Close()
    go server.Serve(listener)
    url := "http://"+listener.Addr().String()+"/"
    if check {
        resp,err:=http.Get(url+"dashboard.json")
        if err!=nil{return err}
        defer resp.Body.Close()
        var records []json.RawMessage
        if err=json.NewDecoder(resp.Body).Decode(&records);err!=nil{return err}
        if len(records)!=84 { return errors.New("study data incomplete") }
        fmt.Println("84 observations verified")
        return nil
    }
    path,err:=browserPath()
    if err!=nil{return err}
    config,err:=os.UserConfigDir()
    if err!=nil{return err}
    profile:=filepath.Join(config,"CQ Land Research","browser")
    if err=os.MkdirAll(profile,0700);err!=nil{return err}
    cmd:=exec.Command(path,"--app="+url+"desktop.html","--user-data-dir="+profile,"--no-first-run","--no-default-browser-check")
    return cmd.Run()
}
func main(){
    if err:=run();err!=nil{
        if runtime.GOOS=="windows" {
            exec.Command("powershell","-NoProfile","-Command",
                "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('无法启动山城地研。请确认已安装 Edge 或 Chrome。')").Run()
        }
        log.Fatal(err)
    }
}
