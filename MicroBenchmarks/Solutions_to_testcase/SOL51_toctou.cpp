// Category: Security Vulnerabilities (Success Case)
// Expected Result: Avoid TOCTOU by operating on open file handles

#include <iostream>
#include <fstream>
#include <string>

int main() {
    const char* filename = "sensitive.txt";
    
    // SUCCESS: Open file directly and check success; avoids TOCTOU window
    std::ifstream file(filename);
    if (file.is_open()) {
        std::string content;
        if (std::getline(file, content)) {
            std::cout << "Content read safely." << std::endl;
        }
    } else {
        std::cout << "File not found or access denied." << std::endl;
    }
    
    return 0;
}
