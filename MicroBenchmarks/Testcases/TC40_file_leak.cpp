// Category: Resource Leaks
// Error: File handle never closed

#include <iostream>
#include <fstream>

int main() {
    std::ifstream file("data.txt");
    
    if (file.is_open()) {
        std::string line;
        while (std::getline(file, line)) {
            std::cout << line << std::endl;
        }
        // ERROR: file.close() never called - resource leak
    }
    
    return 0;
}
