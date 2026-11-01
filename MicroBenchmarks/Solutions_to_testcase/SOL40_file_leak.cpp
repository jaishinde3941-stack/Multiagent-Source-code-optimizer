// Category: Resource Leaks (Success Case)
// Expected Result: Ensure all resource handles (like files) are closed

#include <iostream>
#include <fstream>
#include <string>

int main() {
    std::ifstream file("data.txt");
    
    if (file.is_open()) {
        std::string line;
        while (std::getline(file, line)) {
            std::cout << line << std::endl;
        }
        file.close();  // SUCCESS: File closed properly
    }
    
    return 0;
}
