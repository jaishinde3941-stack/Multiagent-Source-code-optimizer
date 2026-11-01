// Category: Security Vulnerabilities
// Error: Race condition (Time-of-check to time-of-use)

#include <iostream>
#include <fstream>
#include <sys/stat.h>

bool fileExists(const char* filename) {
    struct stat buffer;
    return (stat(filename, &buffer) == 0);
}

int main() {
    const char* filename = "sensitive.txt";
    
    // ERROR: TOCTOU race condition
    // File could be replaced between check and use
    if (fileExists(filename)) {
        std::ifstream file(filename);
        std::string content;
        std::getline(file, content);
        std::cout << "Content: " << content << std::endl;
    }
    
    return 0;
}
